"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) ->  Semantic Evaluator for FR
                           (Factual Recall questions)
-----------------------------------------------------------------------
This module contains production runtime evaluators for question types routed 
through semantic verification pipelines.

The evaluators operate on precomputed tensor artifacts hydrated during
session warmup and return structured DTO payloads containing evaluation
results and runtime telemetry.

The evaluators are designed to:
- minimize unnecessary LLM escalation
- maximize deterministic resolution paths
- support runtime observability via structured trace logging
- operate on pre-hydrated tensor artifacts generated during warmup

Logging in this module is strictly for runtime observability and debugging.
All evaluation state is represented exclusively by returned DTOs.

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
import regex as re

from core.models import RuntimeMCQ_Green, RuntimeMCQ_Blue
from core.preprocessing import count_clean_words
from engine.services.llm_service import call_llm_judge, SYSTEM_PROMPT_FR_SPECIALIST
from engine.services.llm_service import track_eval_latency
from engine.dto import FREvalResults
from engine.evaluators.constants import FRThresholdConfig
from engine.evaluators.helpers import (is_exact_match, compute_fuzzy_match, encode_player_answer,
                                       check_semantic_variations, emit_eval_log)


EVALUATOR_VERSION = "fr_v1"
LLM_JUDGE_SYSTEM_PROMPT = SYSTEM_PROMPT_FR_SPECIALIST
logger = logging.getLogger(__name__)

## FR Answer Evaluator

@track_eval_latency
def check_fr_answer(player_answer: str,
                    q: RuntimeMCQ_Green | RuntimeMCQ_Blue,
                    config: FRThresholdConfig = FRThresholdConfig()
                    ) -> FREvalResults:
    """
    Evaluates a player's Factual Recall (open-text) answer using a 4-Tier logic.
    
    Because FR lacks the safety net of MCQ distractors, this function utilizes a stricter 
    baseline semantic threshold combined with an *entity boost*. It mathematically 
    rescues ambiguous SBERT scores by dynamically injecting domain knowledge (proper nouns) 
    before failing the player.

    The 4 Tiers of Evaluation:
    --------------------------
    - Tier 1 (Exact): Instant pass for perfect string matches (O(1) fast path).
    - Tier 2 (Fuzzy): Levenshtein distance check to catch minor typos.
    - Tier 3 (Semantic & Entity): SBERT cosine similarity check against the Gold Answer 
      and acceptable variations. Dynamically injects a score boost if core proper nouns match.
    - Tier 4 (LLM Specialist): If the player's answer is a statistical length outlier 
      (indicating conversational fluff or lore-dumping), it bypasses Tier 3 and hits 
      a strict LLM Entity Auditor to prevent semantic dilution.
      
    WARNING: Contractual Assumptions
    1. Input Normalization: This function expects `player_answer` and all strings within 
       `entity_refs` to be pre-normalized (lowercased, stripped of trailing whitespace). 
       Do not pass raw user input directly to this method. Use the upstream helper first.  
    2. Tensor Hydration: This function assumes the system has completed the session 
       warmup phase. The `q` object must have its PyTorch tensor matrices fully instantiated.  

    Args:
        player_answer (str): The normalized text input submitted by the player.
        q (ProductionStandard_Green | ProductionStandard_Blue): The strictly-typed Question 
            object containing the gold answer, entity refs, and hydrated tensor matrices.
        config (FRThresholdConfig, optional): The threshold control board for this evaluator. 
            Defaults to standard FR thresholds.
        enable_llm_escalation (bool, optional): Allows routing to the LLM judge for length 
            outliers. Defaults to False.

    Returns:
        FREvalResults: A strictly typed payload containing the verification results 
            and nested telemetry.
    """
    # unpack necessary attributes from the `q` Question object
    question = q.question
    gold_answer = q.answer
    gold_answer_word_count = q.answer_length
    answer_variations = q.answer_variations
    source_quote = q.source_quote or ""  # not available for legacy questions
    explanation = q.explanation
    entity_refs = q.semantic_entity_refs
    
    logger.debug("FR evaluation started", extra={"question_id": q.master_id})
    
    # Type checker & tensor hydration -- confirm preprocessing in place
    gold_ans_tensor = q.answer_embeddings_tensor
    answer_variation_tensor_matrix = q.answer_variations_embeddings_tensor_matrix
    
    if gold_ans_tensor is None:
        logger.error("Missing gold tensor",extra={"question_id": q.master_id})
        raise RuntimeError(f"Missing answer tensor for Question [{q.master_id}]. "
                            "Was hydration skipped?")
    
    if answer_variation_tensor_matrix is None:
        logger.error("Missing answer variations tensor",extra={"question_id": q.master_id})
        raise RuntimeError(f"CRITICAL: Missing variations matrix for Question [{q.master_id}].")
    
    # confirm preprocessing in place
    # normalization of player ans is handled upstream of question_type specific helper
    if not isinstance(player_answer, str):
        logger.error("Invalid player_answer type received",
                     extra={"question_id": q.master_id, "type": type(player_answer).__name__})
        raise TypeError("player_answer must be a normalized string")
    
    # initialize FR metrics results object
    result = FREvalResults()
    
    # TIER 1: fast path (exact match) --> use case: perfect answers
    if is_exact_match(player_answer, gold_answer):
        result.is_correct = True
        result.resolution_tier = 'fr_exact'
        result.fuzzy_score = 1.00
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result

    # TIER 2: intermediate path (fuzzy match -> use case: typos, spelling mistakes in short ans (FR, MCQ)
    result.fuzzy_score = round(compute_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= config.fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "fr_fuzzy"
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result

    # TIER 3: Semantic matching (final resolution path)
    player_tensor = encode_player_answer(player_answer)

    # check similarity of player answer to gold answer, answer variations with helper
    correct_ans_score, matched_variation = check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)
    
    # preload base telemetry (applies to Paths A, B, C)
    result.base_sim_score = round(correct_ans_score, 4)
    result.matched_answer_variation = matched_variation
    
    # Path A: check player answer lengths (if outlier or if too verbose)
    player_ans_wc = count_clean_words(player_answer)
    
    # edge cases routing to LLM judge
    is_outlier = player_ans_wc > config.fr_ans_len_outlier_wc   # exceeds legacy outlier ans word count
    # verbose player ans: if twice the len of expected and wc in vector dilution range of sbert
    is_disproportionate = (player_ans_wc >= 2 * gold_answer_word_count) and (player_ans_wc >= 8) 
        
    if is_outlier or is_disproportionate:
        llm_judgment, executing_model, latency_time, is_success = call_llm_judge(question,
                                                                                 gold_answer, 
                                                                                 player_answer,
                                                                                 answer_variations,
                                                                                 source_quote,
                                                                                 explanation,
                                                                                 system_prompt=LLM_JUDGE_SYSTEM_PROMPT)
    
        if llm_judgment.is_correct:
            result.is_correct = True
            result.resolution_tier = 'fr_llm_judge_pass'
            
        else:
            result.is_correct = False
            result.resolution_tier = 'fr_llm_judge_fail'
        # update result with llm metrics 
        result.llm_model_used = executing_model     
        result.quiz_host_response = llm_judgment.quiz_host_response
        result.evaluation_reasoning = llm_judgment.evaluation_reasoning
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result
            
    # Path B: player answer meets threshold immediatetly
    elif correct_ans_score >= config.semantic_threshold:
        result.is_correct = True
        result.resolution_tier = 'fr_passed_primary_semantic'
        # log telemetery for debugging
        
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result

    # Path C: ambiguous range (boost score if any term matches entity_refs)
    elif correct_ans_score < config.semantic_threshold and correct_ans_score >= config.ambiguous_answer_floor:
        
        # Initialize (prevent UnboundLocalError)
        matched_term = None
        boost_applied = 0.0
        updated_correct_ans_score = correct_ans_score
        
        for entity in entity_refs:
            # use regex with word boundaries matching entity
            pattern = r'\b' + re.escape(entity.lower()) + r'\b'
            if re.search(pattern, player_answer):
                matched_term = entity
                boost_applied = config.entity_ref_match_boost
                updated_correct_ans_score = min(1.00, correct_ans_score + boost_applied) 
                break
        # check updated score against treshold again
        if updated_correct_ans_score >= config.semantic_threshold :
            result.is_correct = True
            result.resolution_tier = 'fr_passed_semantic_boosted'
        else:
            result.is_correct = False
            result.resolution_tier = 'fr_failed_semantic_boosted'
        
        # update common telemetry
        result.boost_applied = boost_applied
        result.matched_entity_ref = matched_term
        result.final_boosted_score = round(updated_correct_ans_score,4)

        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result
    
    # Path D: wrong answer (score below the ambiguous threshold)
    else:
        result.is_correct = False
        result.resolution_tier = "fr_failed_primary_semantic"

        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,logger)
        return result
