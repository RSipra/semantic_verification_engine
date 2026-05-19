"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) ->  Semantic Evaluator for MCQ 
                           (Multiple-Choice Questions)
-----------------------------------------------------------------------
This module contains runtime evaluators for question types routed 
through semantic verification pipelines.

The evaluators operate on precomputed tensor artifacts hydrated during
session warmup and return structured DTO payloads containing evaluation
results and runtime telemetry.

The evaluators are designed to:
- minimize unnecessary LLM escalation
- maximize deterministic resolution paths
- lightweight execution trace logging
- operate on pre-hydrated tensor artifacts generated during warmup

Tracer-phase features include:
-------------------------------
- centralized threshold configuration
- runtime tensor hydration validation
- lightweight execution trace logging
- latency tracking via decorator wrapping
- structured DTO outputs

NOTE:
This module assumes upstream normalization and preprocessing
has already been applied before evaluator routing.

"""
import logging
import torch
from sentence_transformers import util

from core.models import RuntimeMCQ_Green, RuntimeMCQ_Blue
from engine.services.llm_service import track_eval_latency
from engine.dto import MCQEvalResults
from engine.evaluators.constants import MCQThresholdConfig
from engine.evaluators.helpers import (is_exact_match, compute_fuzzy_match, encode_player_answer,
                                       check_semantic_variations, emit_eval_log)

EVALUATOR_VERSION = "mcq_v1"
logger = logging.getLogger(__name__)

### MCQ (multiple choice)

# MCQ with a 'text' answer type (can be evaluated with fuzzy matching and semantic similarity)

@track_eval_latency
def check_mcq_answer(player_answer:str,
                     q: RuntimeMCQ_Green | RuntimeMCQ_Blue,
                     config: MCQThresholdConfig = MCQThresholdConfig()
                     ) -> MCQEvalResults:
    """
    Evaluates a player's multiple-choice answer using a 3-Tier logic.
    
    This function utilizes a 'shift-left' architecture. It relies on precomputed 
    tensor matrices for variations and distractors to evaluate shorthand and 
    partial answers mathematically, without requiring complex string parsing.

    The 3 Tiers of Evaluation:
    --------------------------
    - Tier 1 (Exact): Instant pass for perfect string matches (O(1) fast path).
    - Tier 2 (Fuzzy): Levenshtein distance check to catch minor typos.
    - Tier 3 (Vector): SBERT cosine similarity check against the Gold Answer 
      and an array of acceptable Variations, gated by a Margin delta against Distractors.
      
    WARNING: Contractual Assumption
    1. Input Normalization: This function expects `player_answer` to be pre-normalized 
       (lowercased, stripped of trailing whitespace). Do not pass raw user input directly 
       to this method. Use the `_preprocess_text_player_ans()` upstream helper first.  
    2. Tensor Hydration: This function assumes the system has completed the session 
       warmup phase. The `q` object must have its optional PyTorch tensor matrices 
       (gold answer, variations, and distractors) fully instantiated before evaluation.  

    Args:
        player_answer (str): The normalized text input submitted by the player.
        q (ProductionMCQ_Green): The strictly-typed Question object containing the gold 
            answer and hydrated tensor matrices.
        config (MCQThresholdConfig, optional): The threshold settings for this evaluator. 
            Defaults to standard MCQ thresholds.

    Returns:
        MCQEvalResults: A strictly typed payload containing the verification results 
            and nested telemetry.
    """
    # TODO(tracer): failure_reason taxonomy is simplified for MVP
    # Currently all semantic failures are grouped under: "mcq_failed_semantic"
    #
    # Future improvement:
    # - distinguish "low_similarity" (doesnt match correct answer or distractor)
    #   vs "distractor_conflict" (player picked a distractor)
    # - can capture within 'result.failure_reason: "low_similarity" | "distractor_conflict"'
    # - add observability hooks for threshold tuning
    
    
    # unpack necessary attributes from the `q` Question object
    gold_answer = q.answer
    gold_ans_tensor = q.answer_embeddings_tensor
    answer_variation_tensor_matrix = q.answer_variations_embeddings_tensor_matrix
    distractor_tensor_matrix = q.mcq_distractors_embeddings_tensor_matrix

    logger.debug("MCQ evaluation started", extra={"question_id": q.master_id})

    # --Type checker & Tensor hydration--
    # -> since tensors are Optional in `q` because they are calculated at game warmup
    # but need to be available in game.
    if gold_ans_tensor is None:
        logger.error("Missing gold tensor",extra={"question_id": q.master_id})
        raise RuntimeError(f"Missing answer tensor for Question [{q.master_id}]. "
                           "Was hydration skipped?")

    if answer_variation_tensor_matrix is None:
        logger.error("Missing answer variations tensor",extra={"question_id": q.master_id})
        raise RuntimeError(f"CRITICAL: Missing variations matrix for Question [{q.master_id}].")

    if distractor_tensor_matrix is None:
        logger.error("Missing distractor tensor",extra={"question_id": q.master_id})
        raise RuntimeError(f"CRITICAL: Missing distractor matrix for Question [{q.master_id}].")

    # confirm preprocessing in place
    if not isinstance(player_answer, str):
        logger.error("Invalid player_answer type received",
                     extra={"question_id": q.master_id, "type": type(player_answer).__name__})
        raise TypeError("player_answer must be a normalized string")
    # normalization of player ans is handled upstream of question_type specific helper
    
    # initialize mcq results instance
    result = MCQEvalResults()
    
    # TIER 1: fast path (exact match) --> use case: perfect answers 
    if is_exact_match(player_answer, gold_answer):
        # update and return results 
        result.is_correct = True
        result.resolution_tier = 'mcq_exact'
        result.fuzzy_score = 1.00
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result

    # TIER 2: intermediate path (fuzzy match -> use case: typos, 
    #         spelling mistakes in short ans (FR, MCQ)
    result.fuzzy_score = round(compute_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= config.fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "mcq_fuzzy"
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result

    # TIER 3: semantic logic (resolution path)
    # 1. encode player answer using helper
    player_tensor = encode_player_answer(player_answer)

    # 2. calculate similarity scores (against main gold correct answer, answer variations and find most similar) with helper
    correct_ans_score, matched_variation = check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)

    # 2.2: difference to distractors
    # For the matrix [N, 384], cos_sim returns [1, N]. [0] gets the vector of scores.
    distractor_scores = (util.cos_sim(player_tensor, distractor_tensor_matrix)[0])
    max_dist_score = torch.max(distractor_scores).item()

    margin = correct_ans_score - max_dist_score

    # 3. update results telemetry metrics
    result.sim_correct_ans = round(correct_ans_score,4)
    result.sim_distractor = round(max_dist_score,4)
    result.margin =  round(margin, 4)
    result.matched_answer_variation =  matched_variation # True if a variation (likely shorthand used)

    if correct_ans_score >= config.semantic_threshold and margin >= config.distractor_delta:
        result.is_correct= True
        result.resolution_tier=  "mcq_passed_semantic"

    else:
        result.is_correct = False
        result.resolution_tier = "mcq_failed_semantic"
        
    # emit evaluation log
    emit_eval_log(result, q.master_id, q.question_type,logger)

    return result
