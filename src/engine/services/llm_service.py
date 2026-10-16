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
import os
from functools import wraps
from enum import Enum
from typing import TypedDict, Literal
from dotenv import load_dotenv, find_dotenv
import httpx
from google import genai
from google.genai import types, errors
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
#    - Judge-call signals deferred; see NOTE below call_llm_judge.
#
# NOTE:
# This module should remain stateless and purely evaluative.
# Any persistence, batching, or session reconstruction belongs above this layer.
# =============================================================================

## 1: Models, Constants, Configuration

# Main LLM API Call 
PRIMARY_MODEL =  "models/gemini-3.1-flash-lite"
FALLBACK_MODEL = "models/gemini-flash-latest"

# LLM Judge temperature: low temperature for deterministic evaluation
LLM_JUDGE_TEMPERATURE = 0.1

TRANSIENT_BACKOFF = 10.0
ERROR_COOLDOWN = 4.0 

# Error classification for LLM call outcomes; shared by warmup and judge
class ErrorClass(str, Enum):
    """Category of an LLM call outcome; shared by warmup and judge."""
    NONE = "none"
    TRANSIENT = "transient"
    FAIL_FAST = "fail_fast"
    UNEXPECTED = "unexpected"

# llm warmup health signal 
class LlmWarmupHealth(str, Enum):
    """signal for LLM health from warmup ping at app startup"""
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"

# mapping from error class to warmup health signal
_HEALTH_BY_CLASS: dict[ErrorClass, LlmWarmupHealth] = {
    ErrorClass.NONE: LlmWarmupHealth.OK,
    ErrorClass.TRANSIENT: LlmWarmupHealth.DEGRADED,
    ErrorClass.FAIL_FAST: LlmWarmupHealth.FAILED,
    ErrorClass.UNEXPECTED: LlmWarmupHealth.FAILED,
}

# warmup event record: identical keys for every outcome
class WarmupSignals(TypedDict):
    """Warmup event record consumed by the controller."""
    event_type: Literal["llm_warmup"]
    success: bool
    model: str
    duration_sec: float
    error: str | None
    error_type: str | None
    error_code: int | None
    error_class: ErrorClass
    health: LlmWarmupHealth

# HTTP status codes from google.genai.errors.APIError (.code is an int)
# Transient: worth trying the next model in the cascade
#   429 resource exhausted (rate limit rpm, or daily quota rpd)
#   500/502/504 server-side errors; 503 service unavailable (overloaded)
TRANSIENT_CODES = {429, 500, 502, 503, 504}

# Fail fast: retrying cannot help, fix the request or config instead
#   400 bad request, 401 bad API key, 403 no permission, 404 model not found
FAIL_FAST_CODES = {400, 401, 403, 404}

# --configure API for LLM judge for EX evaluator--
load_dotenv(find_dotenv("config.env"), override=True)
google_api_key = os.environ.get('GEMINI_API_KEY')
if not google_api_key:
    raise ValueError("Error: GEMINI_API_KEY not found.")
client = genai.Client(api_key=google_api_key)

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

# helper to classify LLM errors into transient vs fail-fast
def _classify_error(e: Exception | None) -> ErrorClass:
    """Single source of truth for how an LLM error should be handled."""
    if e is None:
        return ErrorClass.NONE
    if isinstance(e, errors.APIError):
        if e.code in TRANSIENT_CODES:
            return ErrorClass.TRANSIENT
        if e.code in FAIL_FAST_CODES:
            return ErrorClass.FAIL_FAST
        return ErrorClass.UNEXPECTED
    if isinstance(e, httpx.TransportError):
        return ErrorClass.TRANSIENT
    return ErrorClass.UNEXPECTED

# Raise warmup llm health signal for controller action
def signal_llm_health(warmup_system_signals: WarmupSignals) -> LlmWarmupHealth:
    """Translates the warmup event record into a health signal for the controller."""
    return _HEALTH_BY_CLASS.get(warmup_system_signals["error_class"],
                                LlmWarmupHealth.FAILED)

def _build_warmup_signals(model_name: str, duration: float,
                          error: Exception | None = None) -> WarmupSignals:
    """Warmup event record; identical keys for every outcome."""
    error_class = _classify_error(error)
    return WarmupSignals(
        event_type="llm_warmup",
        success=error is None,
        model=model_name,
        duration_sec=duration,
        error=str(error) if error else None,
        error_type=type(error).__name__ if error else None,
        error_code=getattr(error, "code", None),
        error_class=error_class,
        health=_HEALTH_BY_CLASS[error_class],
    )

# warmup function to mitigate cold start latency for the first few LLM calls in the evaluation loop
def warmup_llm_connection(model_name: str = PRIMARY_MODEL, 
                          system_prompt: str = SYSTEM_PROMPT_EX):
    """
    Send one minimal request to open the HTTPS connection held by the shared
    `client`, so the first real evaluation call doesn't pay the setup cost.
    Only effective if later calls reuse the same module-level `client`.
    Run once before the main evaluation loop
    """
    # DEBUG: warmup LLM request boundary marker
    logger.debug("LLM warmup started for model=%s", model_name)
    start_time = time.time()

    try:
        # This mirrors the real judge config (system prompt + JSON schema) so the
        # warmup exercises the same request path. Response is not parsed.
        client.models.generate_content(
            model=model_name,
            contents="Return a dummy response",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=LLMJudgeResponse,
                http_options=types.HttpOptions(timeout=60_000),
                )
            )

        duration = time.time() - start_time
        # helper builds the warmup system signals for the controller as success
        system_signals = _build_warmup_signals(model_name, duration)

        logger.info("LLM warmup successful (model=%s)", model_name)
        logger.debug("Warmup duration: %.2f s", duration)
        return system_signals

    except Exception as e:   # intentionally broad for external API boundary
        duration = time.time() - start_time
        # helpers classify error as transient, fail-fast, or unexpected and
        # build system signals for controller
        signals = _build_warmup_signals(model_name, duration, error=e)
        logger.exception("LLM warmup failed (model=%s, class=%s, code=%s)",
                     model_name, signals["error_class"].value, signals["error_code"])
        return signals

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
# Refactor LLM judge into evaluator-specific wrappers (EX, FR, etc.)
# sharing the single module-level client
#
# Current state:
# - one shared module-level `client`; system_prompt passed per request
#
# Target state:
# - evaluator-specific wrappers (EX, FR) that each hold their system_prompt
#   and share the single module-level `client`
#   (never create a genai.Client per call or per evaluator)
#
# Benefits:
# - fixed system_prompt per evaluator: no cross-contamination between modes
# - cleaner call sites for batch evaluation
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
            logger.debug("Invoking LLM judge (model=%s)", target_model)
            start_time = time.time()
            
            # 2. LLM inference call with structured response schema and timeout
            response = client.models.generate_content(
                model=target_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=LLM_JUDGE_TEMPERATURE,
                    response_mime_type="application/json",
                    response_schema=LLMJudgeResponse,
                    http_options=types.HttpOptions(timeout=60_000),
                    )
                )

            latency_sec = time.time() - start_time
            logger.debug("llm_latency_sec=%.3f", latency_sec)

            # 3. conservative rate Limiting (10 RPM / 6s buffer)
            time.sleep(delay_seconds)
            
            if not response.text:
                raise ValueError(f"Empty response from {target_model}")
            
            # clean markdown formatting before parsing
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            # 4. validation
            payload = LLMJudgeResponse.model_validate_json(raw_text.strip())    
            return payload, target_model, latency_sec, True

        # intentionally broad for external API boundary
        except Exception as e:
            error_class = _classify_error(e)

            if error_class is ErrorClass.TRANSIENT:
                logger.warning("Transient LLM error (model=%s). Switching to next model.",
                            target_model, exc_info=True)
                time.sleep(TRANSIENT_BACKOFF)
                continue

            if error_class is ErrorClass.FAIL_FAST:
                logger.error("Permanent LLM error (model=%s, code=%s). Check request/config.",
                            target_model, getattr(e, "code", None), exc_info=True)
            
            else:  # UNEXPECTED
                logger.error("Unexpected LLM error (model=%s). Failing fast.",
                            target_model, exc_info=True)

            # sleep even on errors to cool down the connection
            time.sleep(ERROR_COOLDOWN) 

            error_payload = LLMJudgeResponse(
                is_correct=False,
                quiz_host_response="The Restricted Section is currently off-limits.",
                evaluation_reasoning=f"System error: {str(e)}")
            return error_payload, target_model, 0.0, False

    # 5. Graceful Degradation if entire cascade fails
    logger.error("LLM cascade exhausted across all models",
                 extra={"question": question,"models_tried": model_cascade})

    logger.warning("Returning fallback LLM response due to full cascade failure.")

    fail_payload = LLMJudgeResponse(is_correct=False,
                                    quiz_host_response="The Floo Network is currently congested.",
                                    evaluation_reasoning="System error: All LLM tiers failed or exceeded quota.")
    return fail_payload, last_model, 0.0, False

# NOTE (observability - deferred by design):
# Unlike warmup_llm_connection, this function does not emit a structured
# signal record (cf. WarmupSignals). This is intentional:
# - Its 4-tuple return is consumed by the EX/FR evaluators; changing it is a
#   contract change across consumers.
# - No controller consumes LLM health signals yet (warmup health is also
#   not integrated), so the record shape would be designed without a consumer.
# Error categories are still applied here via _classify_error, so log output
# carries the same classification as warmup.
#
# Revisit after the controller observability design decides:
# - what the controller does with health (skip tiers, degraded-mode UX, retries)
# - per-call vs per-attempt events for the cascade
# - whether a successful fallback counts as DEGRADED
# - where events go (logs, in-memory buffer, persistence)
# Then: generalize WarmupSignals → LLMCallSignals (event_type: warmup | judge),
# reusing _classify_error and the builder.
