"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) ->  Main Evaluation Router Testing

-----------------------------------------------------------------------
"""

from unittest.mock import patch, Mock
import copy
import pytest

from engine.evaluators.router import evaluation_router, emit_dispatch_log
from tests.unit.test_mcq_evaluator import MCQ_SAMPLE
from tests.unit.test_fr_evaluator import FR_SAMPLE
from tests.unit.test_ex_evaluator import EX_SAMPLE

from game_app.warmup import question_factory

# helper to create Question DTO for tests
def make_question(sample, **overrides):
    """Construct Question object from test sample"""
    payload = copy.deepcopy(sample)
    payload.update(overrides)
    return question_factory(payload, mode="dev")

# helper for mock evaluatoion result return
def make_eval_result(is_correct=True, tier="mock_tier"):
    """creates a mock result that is returned by evaluator"""
    m = Mock()
    m.is_correct = is_correct
    m.resolution_tier = tier
    return m

## happy path: numeric routing

@patch("engine.evaluators.router.check_numeric_answer")
def test_router_for_correct_numeric_ans(mock_num):
    """
    A question with numeric answer will route the player answer to the 
    sturctured numeric evaluator
    """
    # leverage existing sample to create question object
    correct_q = make_question(FR_SAMPLE)
    # replace answer with stringified num
    correct_q.answer = "10"
    correct_q.answer_type = "numeric"
    player_answer = correct_q.answer
    # create mock results dto returned from evaluator
    mock_num.return_value = make_eval_result(True, "numeric_exact_pass")

    result = evaluation_router(player_answer, correct_q)

    mock_num.assert_called_once()
    assert result.is_correct is True
    assert result.resolution_tier == 'numeric_exact_pass'

## Date type routing

@patch("engine.evaluators.router.check_date_answer")
def test_router_for_correct_date_ans(mock_date):
    """
    A question with numeric answer will route the player answer to the 
    sturctured numeric evaluator
    """
    # leverage existing sample to create question object
    correct_q = make_question(FR_SAMPLE)
    # replace answer with stringified num
    correct_q.answer = "10 January 2010"
    correct_q.answer_type = "date"
    player_answer = correct_q.answer
    # create mock results dto returned from evaluator
    mock_date.return_value = make_eval_result(True, "date_exact_pass")

    result = evaluation_router(player_answer, correct_q)

    mock_date.assert_called_once()
    assert result.is_correct is True
    assert result.resolution_tier == 'date_exact_pass'

## MCQ routing

@patch("engine.evaluators.router.check_mcq_answer")
def test_router_for_correct_mcq_ans(mock_mcq):
    """Routes MCQ text answers to the MCQ evaluator."""

    correct_q = make_question(MCQ_SAMPLE)
    player_answer = correct_q.answer
    # setup mcq results dto as patch response
    mock_mcq.return_value = make_eval_result(True,"mcq_exact")

    result = evaluation_router(player_answer, correct_q)

    mock_mcq.assert_called_once()
    assert result.is_correct is True
    assert result.resolution_tier == 'mcq_exact'
    
## FR routing

@patch("engine.evaluators.router.check_fr_answer")
def test_router_for_correct_fr_ans(mock_fr):
    """Routes FR text answers to the FR evaluator."""

    correct_q = make_question(FR_SAMPLE)
    player_answer = correct_q.answer
    # setup fr results dto as patch response
    mock_fr.return_value = make_eval_result(True, "fr_exact")

    result = evaluation_router(player_answer, correct_q)

    mock_fr.assert_called_once()
    assert result.is_correct is True
    assert result.resolution_tier == 'fr_exact'

## EX routing

@patch("engine.evaluators.router.check_ex_answer")
def test_router_for_correct_ex_ans(mock_ex):
    """Routes EX text answers to the EX evaluator."""

    correct_q = make_question(EX_SAMPLE)
    player_answer = correct_q.answer
    # setup EX results dto as patch response
    mock_ex.return_value = make_eval_result(True, "ex_exact")

    result = evaluation_router(player_answer, correct_q)

    mock_ex.assert_called_once()
    assert result.is_correct is True
    assert result.resolution_tier == 'ex_exact'

## Unknown answer type (graceful degredation with fallback)

def test_main_router_unknown_answer_type_fallback():
    """
    Router fallback behavior when Question.answer_type is not in supported AnswerType enum.
    Simulates dataset evolution or schema mismatch where evaluator mapping is missing.
    """
    q = make_question(FR_SAMPLE)
    q.answer_type = "UNSUPPORTED_TYPE"

    result = evaluation_router("some answer", q)

    assert result.is_correct is False
    assert result.resolution_tier == "fallback_unknown_answer_type"

## unknown question type (fail fast failure in text subrouter)

def test_text_subrouter_unknown_question_type_fails():
    """
    An unknown question type reaching the text-subrouter indicates system 
    invariant broken (by e.g. schema drift) and evaluator not present.
    It will raise error and fail fast.
    """
    q = make_question(FR_SAMPLE)
    player_answer = q.answer
    q.question_type = "UNKNOWN QUESTION TYPE"

    with pytest.raises(RuntimeError, 
                       match="Invariant violation: invalid QuestionType reached text subrouter "):
        evaluation_router(player_answer, q)
    
## Empty player answer

def test_main_router_with_empty_player_answer():
    """
    An empty answer will be marked as incorrect and labelled as 
    empty submission
    """
    q = make_question(FR_SAMPLE)
    player_answer = ""

    result = evaluation_router(player_answer,q)

    assert result.is_correct is False
    assert result.resolution_tier == "empty_submission"

## Dispatch logging test

def test_dispatch_log_emits_info():
    """player answer will be dispatched to the FR evaluator"""
    mock_logger = Mock()

    emit_dispatch_log(question_id="q1",
                      question_type="FR",
                      answer_type="TEXT",
                      evaluator="FR",
                      logger_obj=mock_logger)

    mock_logger.info.assert_called_once_with(
            "EVALUATOR_DISPATCH",extra={"question_id": "q1",
                                        "question_type": "FR",
                                        "answer_type": "TEXT",
                                        "evaluator": "FR"
                                       })
