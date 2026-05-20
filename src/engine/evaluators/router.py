"""
===========================================================================
SEMANTIC VERIFICATION ENGINE (Reference Implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) -> Runtime Answer Routing Layer
-----------------------------------------------------------------------

This module implements the *primary routing layer* for runtime answer 
evluation. It is responsible for:
- normalizing raw player input at the system boundary
- dispatching requests to the correct evaluation sub-router
- separating text-based and structured (non-text) evaluation flows
- enforcing type safety and routing invariants
- emitting lightweight dispatch logs for observability

IMPORTANT DESIGN PRINCIPLES
---------------------------
This module does NOT perform semantic evaluation.
All evaluation logic is delegated to downstream evaluators:
- MCQ evaluator
- FR (Factual Recall) evaluator
- EX (Explanatory) evaluator
- Structured evaluators (numeric, date, year)

The router’s responsibility is strictly orchestration and dispatch.

PIPELINE OVERVIEW
------------------
1. Input validation (type safety gate)
2. Global normalization of raw player input
3. Empty-submission handling
4. Answer-type routing (TEXT vs NON-TEXT)
5. Question-type dispatch to evaluator modules
6. Structured logging of routing decisions

PREPROCESSING CONTRACT
----------------------
- Global normalization is applied once at the router boundary.
- Downstream evaluators assume inputs are already normalized.
- Structured evaluators may apply additional type-specific preprocessing
  (e.g. numeric parsing, date extraction).

ROUTING SYSTEM CONTRACT (Failure Modes)
-----------------------

- The main router is the only boundary that handles unknown AnswerTypes
- Subrouters assume validated input and enforce strict invariants
- Any violation of subrouter assumptions is treated as a system error
  (fail-fast), not a recoverable runtime condition  

LOGGING MODEL
-------------
This module emits lightweight dispatch logs only:
- evaluator selection
- question metadata
- answer type routing decision

No evaluation state is computed here; all results originate from evaluators.

Tracer Notes:
-------------
This routing layer is designed to remain deterministic, side-effect light,
and stable under test. It is intentionally kept free of ML logic.
"""

import logging
from typing import cast
import warnings

from core.preprocessing import normalize_value
from core.constants import AnswerType, QuestionType
from core.models import (RuntimeStandard_Green, RuntimeMCQ_Green,
                         RuntimeStandard_Blue, RuntimeMCQ_Blue)
from engine.dto import BaseEvalResults
from engine.evaluators.structured_evaluators import (preprocess_numeric_player_ans,
                                                     check_numeric_answer,
                                                     normalize_date_text,
                                                     extract_date_entities,
                                                     check_date_answer)
from engine.evaluators.mcq_evaluator import check_mcq_answer
from engine.evaluators.fr_evaluator import check_fr_answer
from engine.evaluators.ex_evaluator import check_ex_answer

ROUTER_VERSION = "router_v1"

TEXT_ANSWER_TYPE = AnswerType.TEXT
NON_TEXT_ANSWER_TYPES = {AnswerType.NUMERIC, 
                  AnswerType.YEAR, 
                  AnswerType.DATE}

logger = logging.getLogger(__name__)

## logging helper
# shared logging and result dto return abstraction across evaluators
def emit_dispatch_log(question_id: str,
                      question_type: str,
                      answer_type: str,
                      evaluator: str,
                      logger_obj):
    """
    Emits structured router dispatch log.
        This is a terminal side-effect function:
        - logs summary information
        - attaches trace visibility
        - does NOT modify control flow
        - does NOT return a value
    """
    logger_obj.info("EVALUATOR_DISPATCH", extra={"question_id": question_id,
                                             "question_type": question_type,
                                             "answer_type": answer_type,
                                             "evaluator": evaluator
                                             }
                )

## 1. subrouter for non-text answer evaluation

def _route_nontext_eval(player_answer: str,
                        q: RuntimeStandard_Green | 
                           RuntimeMCQ_Green |
                           RuntimeStandard_Blue |
                           RuntimeMCQ_Blue) -> BaseEvalResults:
    """
    Numeric subrouter:
    -----------------
    - handles all deterministic, strict-match non-textual answers
    - Supported AnswerTypes (enum): NUMERIC, YEAR, and DATE.

    Invariant:
    ----------
    - All inputs MUST have been validated by the main router
    - Only supported AnswerTypes should reach this layer

    Failure mode:
    -------------
    - Any unsupported AnswerType is a system integrity violation
      and will trigger a fail-fast error (no fallback behavior)
    
    """
    # 1. numeric or year answer
    if q.answer_type in [AnswerType.NUMERIC, AnswerType.YEAR]:
        # 1. preprocess the player answer
        processed_player_num = preprocess_numeric_player_ans(player_answer,
                                                             q.answer_type,
                                                             hard_cap=1)
        # 2. route to evaluator
        emit_dispatch_log(q.master_id, q.question_type,q.answer_type,
                          "structured",logger)
        return check_numeric_answer(processed_player_num, q.answer_type, q.answer)

    # 2. date answer
    elif q.answer_type == AnswerType.DATE:
        # 1. preprocess the player answer
        normalized_date = normalize_date_text(player_answer)
        # processed_player_date = _preprocess_date_player_ans(normalized_date, hard_cap=1)
        extracted_date = extract_date_entities(normalized_date)
        # 2. route to evaluator
        emit_dispatch_log(q.master_id, q.question_type,q.answer_type,
                          "structured",logger)
        return check_date_answer(extracted_date, q.answer)

    # 3. catch-all for unknown answer-type
    raise RuntimeError(
        f"Invariant violation: invalid AnswerType reached non-text subrouter: {q.answer_type}")

## 5.2. Subrouter for TEXT type answers
def _route_text_eval(player_answer: str, 
                     q: RuntimeStandard_Green | 
                        RuntimeMCQ_Green |
                        RuntimeStandard_Blue |
                        RuntimeMCQ_Blue):
    """
    Semantic (text) subrouter:
    -------------------------
    - handles text answers routed to semantic evaluators
    - Supported AnswerType (enum): TEXT
    - Supported QuestionType (enum): MCQ, EX, FR

    Invariant:
    ----------
    - All inputs MUST have been validated by the main router
    - Only supported QuestionTypes should reach this layer

    Failure mode:
    -------------
    - Any unsupported QuestionType is a system integrity violation
      and will trigger a fail-fast error (no fallback behavior)
    """
    # 1. Preprocessing (normalize)
    # norm_player_ans = _preprocess_text_player_ans(player_answer)

    # 2. MCQ (Multiple Choice Questions) evaluator
    if (isinstance(q, (RuntimeMCQ_Green, RuntimeMCQ_Blue))
        and q.question_type == QuestionType.MCQ):
        emit_dispatch_log(q.master_id, q.question_type,q.answer_type,"MCQ",logger)
        return check_mcq_answer(player_answer, q)

    # 3. FR (Factual Recall) evaluator
    elif (isinstance(q, (RuntimeStandard_Green, RuntimeStandard_Blue))
          and q.question_type == QuestionType.FR):
        emit_dispatch_log(q.master_id, q.question_type,q.answer_type,"FR",logger)
        return check_fr_answer(player_answer, q)

    # 4. EX (Explanatory) evaluator
    elif (isinstance(q, (RuntimeStandard_Green, RuntimeStandard_Blue))
          and q.question_type == QuestionType.EX):
        emit_dispatch_log(q.master_id, q.question_type,q.answer_type,"EX",logger)
        return check_ex_answer(player_answer, q)

    # 5. Fail fast: unknown QuestionType
    raise RuntimeError(
        f"Invariant violation: invalid QuestionType reached text subrouter {q.question_type}")

## 5.3 Main router for answer checking

def evaluation_router(raw_player_answer,
                      q: RuntimeStandard_Green | 
                         RuntimeMCQ_Green |
                         RuntimeStandard_Blue |
                         RuntimeMCQ_Blue) -> BaseEvalResults:
    """
    Main Evaluation Router: Entry point to the SVE Answer Evaluators. 
    Routes player answers to the appropriate sub-router based on AnswerType.
    
    Responsibilities: Normalize player answer upfront and dispatch questions 
    by AnswerType
    
    Guarantees:
    -----------
    - Only supported AnswerTypes are dispatched to subrouters
    - Unknown AnswerTypes are handled via fallback result (no subrouter call)
    """
    # 1. make sure the player answer is str (gateway shield) - guard for switch from CLI
    if not isinstance(raw_player_answer, str):
        raise TypeError(f"Expected string from interface, got {type(raw_player_answer)}.")

    # 2. use global normalization (symmetric processing) from `qa_validation` pipeline
    #    to match gold ans
    # Note: temporarily mute empty string warnings (needed in validator pipeline but empty
    #    player answer is ok)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clean_player_answer = normalize_value(raw_player_answer)

    # 3. if normalized player answer is None or ""(empty str, ie. player skips with an enter)
    if not clean_player_answer:
        # return as incorrect answer
        return BaseEvalResults(
            is_correct=False,
            resolution_tier="empty_submission")

    # force linter to recognize player ans always a str
    # (not List[str] as can be expected from normalizer in validation pipeline)
    clean_player_answer = cast(str, clean_player_answer)

    # 4. subrouter for text answers to semantic evaluators
    if q.answer_type == TEXT_ANSWER_TYPE:
        result = _route_text_eval(clean_player_answer, q)
        return result

    # 5. subrouter for non-text answers (numeric, year, date)
    elif q.answer_type in NON_TEXT_ANSWER_TYPES:
        result = _route_nontext_eval(clean_player_answer, q)
        return result

    # 6. catch-all failsafe (should never occur; indicates routing invariant violation e.g. schema drift)
    fallback_result = BaseEvalResults(is_correct = False,
                                      resolution_tier = 'fallback_unknown_answer_type')
    logger.warning("Main router encountered unsupported answer type",
                   extra={
                       "question_id": q.master_id,
                       "question_type": q.question_type,
                       "answer_type": q.answer_type
                         }
                  )
    return fallback_result
