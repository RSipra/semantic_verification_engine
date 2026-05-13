"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Unit tests for DTO layer in the Semantic Verification Engine.
-----------------------------------------------------------------------
This module validates the structure of evaluation result objects
constructed directly by the Evaluator layer.

Key principles:
- DTOs are internal evaluator-owned data structures representing evaluation outputs
- All DTO instances are constructed in-code by Evaluators (not parsed from external input)
- Validation focuses on structural correctness and type integrity only
- No evaluation logic (e.g. similarity scoring, thresholds, or decision rules)
  is tested in this layer

LLM schema contract:
- LLMJudgeResponse defines the structured output schema used for LLM API calls
  during inference-time evaluation
- It is not an evaluation result, but a generation-time contract used by the LLM
  to produce structured reasoning, classification, and UX-facing responses
"""

import pytest
from pydantic import ValidationError
from engine.dto import BaseEvalResults, MCQEvalResults, FREvalResults, EXEvalResults, LLMJudgeResponse

## --- 1.  LLMJudgeResponse ----
# happy response
def test_llm_judge_response_happy_path():
    """Valid LLM judge response should be constructed successfully."""
    result = LLMJudgeResponse(
        evaluation_reasoning="step-by-step logic",
        quiz_host_response="Nice!",
        is_correct=True
    )

    assert result.is_correct is True
    assert result.quiz_host_response == "Nice!"

## --- 2.  Evaluation Results ----

## 1.1. BaseEvalResults 

# happy path
def test_base_eval_results_defaults():
    """Base evaluation results should initialize with correct default values."""
    result = BaseEvalResults()

    assert result.is_correct is False
    assert result.resolution_tier == "unresolved"
    assert result.fuzzy_score == 0.0

# invalid types
def test_base_eval_results_invalid_types():
    """BaseEvalResults should reject invalid field types."""

    with pytest.raises(ValidationError):
        BaseEvalResults(resolution_tier=20)

## 1.2. Multiple Choice Questions (MCQ) 

# happy path
def test_mcq_eval_results_happy_path():
    """MCQ evaluation result should correctly store similarity and margin values."""

    result = MCQEvalResults(sim_correct_ans = 0.90,
                            sim_distractor= 0.4,
                            margin = 0.50,
                            matched_answer_variation = False,
                            execution_time_sec= 0.0001)
    # Assert
    assert result.margin == pytest.approx(0.5)
    assert result.sim_correct_ans > result.sim_distractor
    assert result.is_correct is False or result.is_correct is True
    
# invalid types
def test_mcq_eval_results_invalid_types():
    """MCQEvalResults should raise ValidationError for invalid field types."""

    with pytest.raises(ValidationError):
        MCQEvalResults(sim_correct_ans = "low",  
                       sim_distractor= "high",
                       margin = "ok",
                       matched_answer_variation = "unknown",
                       execution_time_sec= "very fast"
                       )
        
## 1.3. Factual Recall (FR)

# happy path
def test_fr_eval_results_happy_path():
    """FR evaluation result should correctly compute boosted score relationships."""

    result = FREvalResults(base_sim_score = 0.7,
                           matched_answer_variation = False,
                           matched_entity_ref= None,
                           boost_applied = 0.10,
                           final_boosted_score = 0.8,
                           llm_model_used = None,
                           quiz_host_response= "",
                           evaluation_reasoning= "",
                           execution_time_sec= 0.00001)

    assert result.boost_applied == pytest.approx(0.1)
    assert result.final_boosted_score == pytest.approx(0.8)
    assert result.final_boosted_score > result.base_sim_score
    assert result.is_correct is False or result.is_correct is True
    
 # invalid types
def test_fr_eval_results_invalid_types():
    """FREvalResults should reject invalid field types."""

    with pytest.raises(ValidationError):
        FREvalResults(base_sim_score = "0.7",
                      quiz_host_response= 20
                      )

## 1.4. Explanatory (EX)

# happy path
def test_ex_eval_results_happy_path():
    """EX evaluation result should correctly store similarity, NLI, and metadata fields."""
   
    result = EXEvalResults(primary_similarity_score = 0.65,
                           matched_answer_variation= False,
                           nli_label= "",
                           nli_confidence = 0.0,
                           llm_model_used= "gemini-pro",
                           quiz_host_response = "well done",
                           evaluation_reasoning = "correct",
                           execution_time_sec = 1.5)

    assert result.primary_similarity_score == 0.65
    assert result.quiz_host_response == 'well done'
    assert result.is_correct is False or result.is_correct is True
    
 # invalid types
def test_ex_eval_results_invalid_types():
    """EXEvalResults should reject invalid field types."""

    with pytest.raises(ValidationError):
        EXEvalResults(quiz_host_response = True,
                      evaluation_reasoning = 25)
               