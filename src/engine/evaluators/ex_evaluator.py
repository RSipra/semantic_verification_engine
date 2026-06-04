"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) ->  Semantic Evaluator for EX
                           (Explanatory questions)
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

Logging in this module is strictly for runtime observability and debugging.
All evaluation state is represented exclusively by returned DTOs.

Tracer-phase features include:
-------------------------------
- centralized threshold configuration
- runtime tensor hydration validation
- lightweight execution trace logging
- latency tracking via decorator wrapping
- structured DTO outputs

Architecture Reference
-------------------------------
Evaluator workflow diagram for this module are documented in:
    
/assets/docs/phase2/ex_evaluator_logic_v0-1.jpg

The schematic represents the intended runtime routing logic
for the tracer-phase semantic evaluation engine.

NOTE:
This module assumes upstream normalization and preprocessing
has already been applied before evaluator routing.
- NLI disabled for tracer until composite answer claims implemented.

TODO:
surface LM availability and execution status into evaluation telemetry
once runtime observability UI is implemented
"""

import logging
import numpy as np

from core.models import RuntimeStandard_Blue, RuntimeStandard_Green
from core.embeddings import nli_settings #, get_nli_model
from core.preprocessing import count_clean_words
from engine.services.llm_service import call_llm_judge, SYSTEM_PROMPT_EX
from engine.services.llm_service import track_eval_latency
from engine.dto import EXEvalResults
from engine.evaluators.constants import EXThresholdConfig
from engine.evaluators.helpers import (is_exact_match, compute_fuzzy_match, encode_player_answer,
                                       check_semantic_variations, emit_eval_log)

EVALUATOR_VERSION = "ex_v1"
LLM_JUDGE_SYSTEM_PROMPT = SYSTEM_PROMPT_EX

logger = logging.getLogger(__name__)
# nli_model = get_nli_model()

## Helpers
# nli evaluation of answer if sbert ambiguous
# assuming: from sentence_transformers import CrossEncoder
# nli_model = CrossEncoder('cross-encoder/nli-deberta-v3-small')
def _check_nli_entailment(premise: str, hypothesis: str, nli_model_inst) -> tuple[bool, str, float]:
    """
    Evaluates directional semantic entailment between the canonical
    gold answer (premise) and the player response (hypothesis)
    using a cross-encoder NLI model.
    """
    # 1. run NLI cross-encoder
    scores = nli_model_inst.predict([(premise, hypothesis)])[0]

    # 2. convert logits to probabilities using softmax (optional, but good for telemetry)
    probabilities = np.exp(scores) / np.sum(np.exp(scores))

    # 3. get winning id (cast to native int for dict lookup)
    predicted_class_id = np.argmax(probabilities).item()
    confidence = probabilities[predicted_class_id]

    # 4. map id to label using our SOT nli from settings.py
    predicted_label = nli_settings.label_mapping.get(predicted_class_id, "unknown")
    
    # 5. determine success (only if tag is 'entailed')
    is_entailed = (predicted_label == "entailment")
    
    return is_entailed, predicted_label, float(confidence)

## EX Answer Evaluator

# MAIN EX Evaluator 
@track_eval_latency  
def check_ex_answer(player_answer: str,
                    q: RuntimeStandard_Green | RuntimeStandard_Blue,
                    config: EXThresholdConfig = EXThresholdConfig(),
                    enable_nli_escalation:bool = False  #Disabled for the Tracer
                    ) -> EXEvalResults:
    """
    Evaluates explanatory (EX) trivia answers through a multi-tier NLP routing matrix.

    This function optimizes compute by resolving simple matches locally and only
    escalating complex logical or lore-based abstractions to an external language 
    model API. For the current Tracer iteration, this utilizes Gemma 4 via Vertex AI 
    (zero-cost open-weights), but the routing architecture is modular to support 
    interchangeable SLMs/LLMs in future development.

    The 4 Tiers of Evaluation:
    --------------------------
    - Tier 1/2: O(1) Exact and Fuzzy string matching.
    - Tier 3.1: SBERT vector similarity (filters vocabulary mismatches, features Verbosity Bypass).
                vague answers (below ambiguous cutoff) and verbose are directly sent to LLM.
    - Tier 3.2: NLI Cross-Encoder (gates inverted logic and contradictions) -DISABLED for tracer
    - Tier 4: LLM Judge escalation for the ambiguous region (vague abstractions/deep lore).
        
    WARNING: Contractual Assumptions
    1. Input Normalization: This function expects `player_answer` to be pre-normalized 
       (lowercased, stripped of trailing whitespace). Do not pass raw user input directly. 
    2. Tensor Hydration: This function assumes the system has completed the session warmup 
       phase. The `q` object must have its PyTorch tensor matrices fully instantiated.

    Args:
        player_answer (str): The normalized text input provided by the user.
        q (ProductionStandard_Green | ProductionStandard_Blue): The strictly-typed Question 
            object containing the gold answer, legacy UI data, and hydrated tensor matrices.
        config (EXThresholdConfig, optional): The threshold control board for this evaluator. 
            Defaults to standard EX thresholds.
        enable_llm_escalation (bool, optional): Toggle to activate/deactivate the Tier 4 
            LLM judge for A/B testing. Defaults to True.
        enable_nli_escalation (bool, optional): Toggle to activate/deactivate the Tier 3.2 
            NLI logic gate. Defaults to False. NOTE: enable_nli_escalation currently reserved 
            for future implementation. NLI execution is disabled in the Tracer build.

    Returns:
        EXEvalResults: A populated telemetry object containing the final boolean judgment 
            (`is_correct`), the exact pipeline exit node (`resolution_tier`), and 
            internal NLP scores.
    """
    # unpack necessary attributes from the `q` Question object
    question = q.question
    gold_answer = q.answer
    gold_answer_wordcount = q.answer_length
    answer_variations = q.answer_variations
    source_quote = q.source_quote or ""
    explanation = q.explanation
    gold_ans_tensor = q.answer_embeddings_tensor
    answer_variation_tensor_matrix = q.answer_variations_embeddings_tensor_matrix

    # Type checker & tensor hydration -- confirm preprocessing in place
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

    # initialize EX metrics results object
    result = EXEvalResults()

    # TIER -1: exact match, grab any O(1) wins
    if is_exact_match(player_answer, gold_answer):
        result.is_correct = True
        result.resolution_tier = 'ex_exact'
        result.fuzzy_score = 1.00
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,q.answer_type, logger)
        return result
    
    # TIER-2: fuzzy match, grab any O(1) wins
    result.fuzzy_score = round(compute_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= config.fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "ex_fuzzy"
        # emit evaluation log
        emit_eval_log(result, q.master_id, q.question_type,q.answer_type, logger)
        return result

    # TIER-3: semantic resolution (SBERT + NLI)
    player_tensor = encode_player_answer(player_answer)
    # check similarity of player answer to gold answer, answer variations
    correct_ans_score, matched_variation = check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)
    # preload base telemetry 
    result.primary_similarity_score = round(correct_ans_score,4)
    result.matched_answer_variation = matched_variation
    
    player_answer_wordcount = count_clean_words(player_answer)
    len_ratio = player_answer_wordcount / max(1, gold_answer_wordcount)

    # Tier 3.1: primary semantic check
    # verbosity bypass to the LLM
    if correct_ans_score < config.ambiguous_answer_floor:
        if len_ratio >= 2.0 :
            llm_judgment, executing_model, llm_t_sec, _ = call_llm_judge(question,
                                                                 gold_answer, 
                                                                 player_answer,
                                                                 answer_variations,
                                                                 source_quote, 
                                                                 explanation,
                                                                 SYSTEM_PROMPT_EX)
            if llm_judgment.is_correct:
                result.is_correct = True
                result.resolution_tier = 'ex_llm_judge_long_ans_pass'           
            else:
                result.is_correct = False
                result.resolution_tier = 'ex_llm_judge_long_ans_fail'
            # store llm telemetry for both outcomes
            result.llm_model_used=executing_model
            result.quiz_host_response = llm_judgment.quiz_host_response
            result.evaluation_reasoning = llm_judgment.evaluation_reasoning
            result.llm_eval_time_sec = llm_t_sec
            # emit evaluation log
            emit_eval_log(result, q.master_id, q.question_type,q.answer_type, logger)
            return result
        else:
            result.is_correct = False
            result.resolution_tier = 'ex_primary_semantic_fail'
            # emit evaluation log
            emit_eval_log(result, q.master_id, q.question_type,q.answer_type, logger)
            return result
        
    # Tier 3.2: NLI cross-encoder labelling /logic check (disabled in tracer phase)
    # NOTE: retained for architecture parity with evaluator design
    if False:# enable_nli_escalation:
        _, nli_label, nli_confidence = _check_nli_entailment(
                premise=gold_answer,
                hypothesis=player_answer,
                nli_model_inst=nli_model # type: ignore
            )
        # append NLI telemetry to your result object
        result.nli_label = nli_label
        result.nli_confidence = round(nli_confidence,4)

        # contradiction fail fast
        if nli_label == 'contradiction':
            result.is_correct = False
            result.resolution_tier = 'ex_nli_contradiction_fail'
            # emit evaluation log
            emit_eval_log(result, q.master_id, q.question_type,q.answer_type, logger)
            return result

        # entailment pass (high vocab, high directional logic)
        if nli_label == 'entailment' and result.primary_similarity_score >= config.semantic_threshold:
            result.is_correct = True
            result.resolution_tier = 'ex_nli_entailment_pass'
            # emit evaluation log
            emit_eval_log(result, q.master_id, q.question_type,q.answer_type, logger)
            return result

    # Tier 4: LLM resolution for remaining cases
    #         all 'neutral' AND 'entailment' with ambiguous sbert scores 
    #         (i.e. semantic_threshold < sbert_score <= ambiguous_cutoff)
    # EX intentionally avoids direct SBERT-only acceptance.
    # High-similarity answers continue through NLI/LLM routing
    # to validate logical consistency and abstraction handling.

    llm_judgment, executing_model, llm_t_sec, _ = call_llm_judge(question,
                                                         gold_answer, 
                                                         player_answer,
                                                         answer_variations, 
                                                         source_quote, 
                                                         explanation,
                                                         SYSTEM_PROMPT_EX)

    if llm_judgment.is_correct:
        result.is_correct = True
        result.resolution_tier = 'ex_llm_judge_pass'
    else:
        result.is_correct = False
        result.resolution_tier = 'ex_llm_judge_fail'
    # update llm metrics
    result.llm_model_used = executing_model
    result.quiz_host_response = llm_judgment.quiz_host_response
    result.evaluation_reasoning = llm_judgment.evaluation_reasoning
    result.llm_eval_time_sec = llm_t_sec
    # emit evaluation log
    emit_eval_log(result, q.master_id, q.question_type,q.answer_type, logger)       
    return result
