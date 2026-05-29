"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
LLM Service Layer(Tracer Build) -> API calls, EX, FR final tier resolution 
-----------------------------------------------------------------------

This module provides a thin abstraction over external LLM inference APIs
used by the semantic evaluation system (EX + FR evaluators).

It is responsible for:
- Executing LLM inference requests via Gemini API
- Managing model cascade (primary → fallback)
- Handling retries, rate limiting, and transient failures
- Normalizing LLM outputs into structured DTOs (LLMJudgeResponse)
- Measuring per-call latency for downstream observability

DESIGN PRINCIPLES:
- Stateless: no session tracking or persistence is performed here
- External boundary only: all calls are treated as unreliable network I/O
- Fail-soft: errors are converted into structured fallback responses
- Deterministic formatting: raw LLM outputs are sanitized before parsing

NOT RESPONSIBLE FOR:
- Session logging or evaluation history
- Aggregation of results across questions
- Game-level pacing or user experience timing
- Observability pipelines or persistence layers

CONSUMERS:
- EX Evaluator (logical reasoning checks)
- FR Evaluator (factual recall checks)
- Any future semantic evaluation pipelines requiring LLM judgment   

TODO:
integrate warmup health signals to optionally bypass
LLM calls during known outage/degraded states

"""

import time
import logging
from functools import wraps
import pandas as pd
from enum import Enum
import google.generativeai as genai
from regex import F
from engine.dto import LLMJudgeResponse

logger = logging.getLogger(__name__)

# =============================================================================
# TRACER / OBSERVABILITY REFACTOR (POST-MVP)
# =============================================================================
# TODO (high priority after MVP stabilization):
#
# 1. Session Logger Layer
#    - Persist full evaluation sessions (question, answer, result, latency, model)
#    - Enable offline replay/debugging of demo sessions
#    - Support export of session reports (JSON/Parquet)
#
# 2. Game Controller / Router Delay Abstraction
#    - Move LLM rate-limit delay (delay_seconds) out of evaluator layer
#    - Introduce dynamic pacing at controller level
#    - Goal: hide API cooldown latency from user experience
#      (smooth gameplay instead of visible waiting)
#
# 3. Observability Separation
#    - Decouple logging from evaluation logic
#    - Introduce structured event stream (EvaluatorEvent / SessionEvent)
#    - Prepare for cloud persistence layer (VM-safe session recovery)
#
# NOTE:
# This module should remain stateless and purely evaluative.
# Any persistence, batching, or session reconstruction belongs above this layer.
# =============================================================================

## 1: Models, Constants, Configuration

# Main LLM API Call 
PRIMARY_MODEL = "models/gemini-3.1-flash-lite"
FALLBACK_MODEL = "models/gemini-flash-latest"

TRANSIENT_BACKOFF = 10.0
ERROR_COOLDOWN = 4.0 

# llm warmup health signal 
class llm_warmup_health(str, Enum):
    """signal for LLM health from warmup ping at app startup"""
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"

# error 429: resource exchausted (exceeded API usage limits rpm or rpd)
# error 503: service unavailable (server temporarily overloaded, down)
TRANSIENT_CODES = {"429", "503", "timeout", "deadline"}
FAIL_FAST_CODES = {"404", "400", "401", "403"}    

## 2: Prompts

# system prompt for EX (explantory questions) LLM judge
SYSTEM_PROMPT_EX = """
You are an objective Logic Validator for a trivia system.
Your task is to determine if the Player's Guess semantically entails the causal logic and core meaning of the Ground Truth Context.

EVALUATION RULES:
1. DIRECTIONALITY & CAUSALITY: Strictly check the active/passive flow. If the player inverts the subject and the object (e.g., "A caused B" instead of "B caused A"), it is INCORRECT.
2. THEMATIC ADJACENCY IS NOT EQUIVALENCE: Do not pass answers that are merely in the same thematic neighborhood (e.g., "fearing" a concept is not the same as "understanding" it). The core logical meaning must align.
3. CONTEXTUAL INTENT & PRONOUNS: If a player uses vague pronouns (e.g., "he", "it", "they") or partial explanations, you may evaluate them as CORRECT only if the context of their answer makes their logical intent undeniable. Do not penalize conversational shorthand if the causal meaning is clear.
4. FORGIVENESS OF STRUCTURE & OMISSIONS: Accept typos, passive voice (e.g., evaluating "Action B was performed by Entity A" as equivalent to "Entity A performed Action B"), and partial explanations, provided the core causal action is present and not contradicted. If a player omits a minor detail but captures the main action, do NOT penalize them.
5. CRITICAL ANTI-RECITATION RULE: You must write your `reasoning` and `mc_dialogue` using your own original phrasing. Do not quote the source material directly.

Chain of Thought Directive:
In your `reasoning` field, objectively map the causal logic and flow of the Player's Guess against the Ground Truth. If there is a causal inversion, missing core entity, or thematic mismatch, you must evaluate `is_correct` as false.

In your `mc_dialogue` field, act as an engaging, sympathetic trivia host reacting to the player's attempt.
"""

# system prompt for FR (Factual Recall) LLM judge
SYSTEM_PROMPT_FR_SPECIALIST = """
You are an objective Data Validator for a trivia system. 
Your task is to verify if the Player Guess contains the factual entities required by the Ground Truth Context.

EVALUATION RULES:
1. STRICT PROPER NOUN IDENTITY: If the ground truth requires a specific named entity (e.g., 'Ron Weasley', 'Purge & Dowse'), the player must provide that specific entity. 'Percy Weasley' or a broad answer like 'London' is a FATAL MISMATCH.
2. SEMANTIC EQUIVALENCE FOR ACTIONS/DESCRIPTORS: You MUST accept synonyms, paraphrasing, and alternate framings for non-proper nouns. (e.g., "not losing appendages" is semantically equivalent to "keeping remaining limbs"). Do not penalize grammatical framing.
3. FLUFF NEUTRALITY: Ignore conversational intros, extra lore, and subjective adjectives (e.g., 'nerdy and annoying') as long as the core required entities are present and accurate.

Chain of Thought Directive:
In your `reasoning` field, first check for Proper Noun identity. If the specific names/places match, or if the core concepts are semantically equivalent, you must evaluate `is_correct` as true.
"""    

## 3: Helpers

# identify if exception is because of transient error
def _is_transient_error(e: Exception | str | None) -> bool:
    msg = str(e or "").lower()
    return any(code in msg for code in TRANSIENT_CODES)

# Raise warmup llm health signal for controller action
def signal_llm_health(warmup_system_signals: dict):
    """Translates the warmup outcome into a health signal for the controller."""

    if warmup_system_signals.get('success'):
        return llm_warmup_health.OK

    if _is_transient_error(warmup_system_signals.get("error","")):
        return llm_warmup_health.DEGRADED

    return llm_warmup_health.FAILED

# warmup function to mitigate cold start latency for the first few LLM calls in the evaluation loop
def warmup_llm_connection(model_name: str = PRIMARY_MODEL, 
                          system_prompt: str = SYSTEM_PROMPT_EX):
    """
    Standalone network ping to absorb the 6-second gRPC cold-start penalty.
    Run this once before the main evaluation loop.
    """
    # DEBUG: warmup LLM request boundary marker
    logger.debug("LLM warmup started for model=%s", model_name)
    start_time = time.time()
    duration = None

    try:
        # 1. Initialize the model using your exact genai syntax 
        #    System instructions for EX (most LLM calls) added upfront to avoid cold start penalty
        #    on the first real evaluation call.
        ping_model = genai.GenerativeModel( # type: ignore
            model_name=model_name,
            system_instruction=system_prompt
            )

        # 2. Send the smallest possible payload to open the connection and 
        #    compile the response schema (LLMJudgeResponse) to mitigate the 
        #    cold start penalty for future calls.
        _ = ping_model.generate_content(
            "Return a dummy response",
            generation_config=genai.GenerationConfig(  # type: ignore
                response_mime_type="application/json",
                response_schema=LLMJudgeResponse, 
            )
        )

        duration = time.time() - start_time
        
        system_signals = {"event_type": "llm_warmup",
                          "success": True,  # warmup completed end-to-end, usable baseline established
                          "model": model_name,
                          "duration_sec": duration,
                          "error": None}
        system_signals['health'] = signal_llm_health(system_signals)
        
        logger.info("LLM warmup successful (model=%s)", model_name)
        logger.debug("Warmup duration: %.2f s", duration)
        return system_signals

    except Exception as e:   # intentionally broad for external API boundary
           
        system_signals = {"event_type": "llm_warmup",
                          "success": False,  #  warmup failed at any stage (init OR request OR parse)
                          "model": model_name,
                          "duration_sec": None,
                          "error": str(e)}
        
        system_signals['health'] = signal_llm_health(system_signals)
        logger.exception("LLM warmup failed for model=%s", model_name)
        return system_signals
    
# decorator for timing llm calls
def track_eval_latency(func):
    """
    A decorator that intercepts the execution of an evaluator function,
    calculates the total latency, and dynamically injects it into the 
    returned EXEvalResults object.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()

        # Execute the main function (this runs all your Tier 1-4 logic)
        result = func(*args, **kwargs)

        # Calculate latency and inject it before returning to the Tracer loop
        latency = time.perf_counter() - start_time
        if result is not None:
            result.execution_time_sec = round(latency, 4)
        
        return result
    return wrapper

def _build_prompt_context(gold_answer: str, 
                          answer_variations: list, 
                          explanation: str, 
                          source_quote: str|None) -> str:
    """
    Dynamically constructs the ground truth context block for the LLM judge.

    This helper function aggregates the definitive answers, acceptable aliases, 
    and lore explanations into a strictly formatted string. It optimizes the prompt 
    by conditionally injecting the exact source text quote only if it is available 
    (e.g., from the synthetic generation pipeline), gracefully falling back to the 
    detailed explanation for legacy dataset entries.

    Args:
        gold_answer (str): The primary correct answer string from the dataset.
        answer_variations (list): A list of acceptable canonical alternate answers.
        explanation (str): The detailed lore explanation of why the answer is correct.
        source_quote (str): The canonical text quote verifying the answer. Handled safely 
                            if missing (e.g., evaluates to Pandas NaN or literal "<NA>").

    Returns:
        str: A formatted context block designed to be injected directly into the user prompt.
    """
    # type safety
    answer_variations = answer_variations or []
    
    # base context for every question evaluation
    context = f"""
    [GROUND TRUTH CONTEXT]
    Gold Answer: {gold_answer}
    """
    # conditionally append the answer variations if list is not empty (reduce LLM noise)
    if answer_variations:
        context += f"Acceptable Variations: {', '.join(answer_variations)}\n"
    
    context += f"Explanation: {explanation}\n"
    
    # conditionally append the quote only if it exists (for synthetic data)
    if isinstance(source_quote, str) and source_quote.strip():
        context += f'    Source Text Quote: "{source_quote}"\n'

    return context

## 4: LLM Judge API call

# TODO (optimization - Phase 2):
# Refactor LLM judge architecture to create separate LLM client instances
# for each evaluator type (EX, FR, etc.)
#
# Current state:
# - _call_llm_judge receives system_prompt dynamically
# - model is re-instantiated per call
#
# Target state:
# - Create evaluator-specific LLM clients:
#     - EX_LLM_CLIENT (system_prompt = SYSTEM_PROMPT_EX)
#     - FR_LLM_CLIENT (system_prompt = SYSTEM_PROMPT_FR_SPECIALIST)
#
# Benefits:
# - avoid repeated GenerativeModel initialization
# - enable system_prompt caching at client level
# - improve throughput for batch evaluation
# - reduce per-call overhead in cascade scenarios
# 
# Future interface idea:
# class LLMJudgeClient:
#     def __init__(self, model_name, system_prompt)
#     def generate(...)
# Note:
# Must ensure no cross-contamination between evaluator modes.

def call_llm_judge(question: str, 
                    gold_answer: str, 
                    player_answer: str,
                    answer_variations: list,
                    source_quote: str,
                    explanation: str,
                    system_prompt: str,
                    delay_seconds: float = 6.0) -> tuple[LLMJudgeResponse, str, float, bool]:
    """
    Executes an LLM-based evaluation of a trivia response using a cascading model strategy.

    This function supports both EX (explanatory reasoning) and FR (factual recall) evaluation
    modes depending on the provided system prompt. It attempts inference using a primary model
    and falls back to a secondary model if needed.

    Args:
        question (str): The original trivia question presented to the player.
        gold_answer (str): The canonical correct answer.
        player_answer (str): The answer provided by the player.
        answer_variations (list): Acceptable alternate phrasings or aliases for 
            the gold answer.
        source_quote (str):Optional supporting dataset quote used for grounding
            evaluation.
        explanation (str):Ground-truth explanation of the correct answer.
        system_prompt (str): Evaluator-specific instruction set (EX or FR logic).
        delay_seconds (float, optional): Sleep interval between calls for rate 
            limiting. Defaults to 6.0.

    Returns:
        tuple[LLMJudgeResponse, str, float, bool]:
            A tuple containing:
            - LLMJudgeResponse: Structured LLM evaluation output including 
              correctness, reasoning, and host response text.
            - str:The model used to generate the response
              (primary, fallback, or cascade failure marker).
            - float: Latency of the LLM call in seconds
              (excludes warmup and retry overhead).
            - bool: Success flag indicating whether a valid LLM response
              was successfully obtained.

    Raises:
        None: All exceptions are handled internally. Failures return a
            structured fallback response instead of raising errors.
    """
    # 1. configuration for resilience 
    model_cascade = [PRIMARY_MODEL, FALLBACK_MODEL]

    user_prompt = f"""
    [EVALUATION TASK]
    Question: {question}
    Player Guess: {player_answer}
    
    {_build_prompt_context(gold_answer, answer_variations, explanation, source_quote)}           
    """
    last_model = "" # for logging and error catching
    for target_model in model_cascade:
        last_model = target_model
        try:
            # initialize the Gemma model
            model = genai.GenerativeModel( #  type: ignore
                model_name=target_model, 
                system_instruction=system_prompt
            )
            logger.debug("Invoking LLM judge (model=%s)", target_model)
            start_time = time.time()
            
            response = model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(  # type: ignore
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=LLMJudgeResponse, ),
                request_options={"timeout": 60.0}
            )
            latency_sec = time.time() - start_time
            logger.debug("llm_latency_sec=%.3f", latency_sec)

            # 2. conservative rate Limiting (10 RPM / 6s buffer)
            time.sleep(delay_seconds)
            
            # clean markdown formatting before parsing
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            # 3. validation
            payload = LLMJudgeResponse.model_validate_json(raw_text.strip())    
            return payload, target_model, latency_sec, True

        except Exception as e:
            
            # catch transient errors: Rate Limits (429), Timeouts (deadline), Server Errors (503/500)
            if _is_transient_error(e):
                logger.warning("Transient LLM error (model=%s).  Will retry with next model.", target_model, exc_info=True)
                logger.info("Switching to next model in cascade")
                time.sleep(TRANSIENT_BACKOFF)
                continue # <-- pushes it to  FALLBACK_MODEL
            
            time.sleep(ERROR_COOLDOWN) # sleep even on errors to cool down the connection
            
            # non-retryable error → fail fast
            logger.error("Non-retryable LLM error (model=%s). Failing fast.", target_model, exc_info=True)
            error_payload = LLMJudgeResponse(
                is_correct=False,
                quiz_host_response="The Restricted Section is currently off-limits.",
                evaluation_reasoning=f"System error: {str(e)}")
            return error_payload, target_model, 0.0, False
            
    # 4. Graceful Degradation if entire cascade fails
    logger.error("LLM cascade exhausted across all models",
                 extra={"question": question,"models_tried": model_cascade})

    logger.warning("Returning fallback LLM response due to full cascade failure.")
    
    fail_payload = LLMJudgeResponse(is_correct=False,
                                    quiz_host_response="The Floo Network is currently congested.",
                                    evaluation_reasoning="System error: All LLM tiers failed or exceeded quota.")
    return fail_payload, last_model, 0.0, False
