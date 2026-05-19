"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for the FR Semantic Evaluator
-----------------------------------------------------------------------
FR EVALUATOR — CONTRACT TEST SUITE

Validates tiered MCQ evaluation logic under runtime conditions.

Evaluation pipeline:
1. Exact match
2. Fuzzy match (edit distance)
3. Semantic similarity (SBERT with score boost for alias detection)
4. LLM escalation path for outliers (verbose player answers or 
   outlier gold answer length)

Tests assume fully hydrated runtime question objects (FR),
constructed via warmup factory with precomputed embeddings.

Focus:
- correctness of tier routing
- semantic fallback behavior (mocked SBERT and LLM layer)
- enforcement of runtime input contracts
- robustness against invalid or missing tensor state   
"""

from unittest.mock import patch, Mock
import copy
import pytest
import numpy as np
from engine.evaluators.fr_evaluator import check_fr_answer
from game_app.warmup import question_factory

## fixtures

LLM_PATH = "engine.evaluators.fr_evaluator.call_llm_judge"
SBERT_PATH = "engine.evaluators.fr_evaluator.check_semantic_variations"

# actual sample question from runtime tracer dataset (ProductionMCQ_Green)
def fake_embedding():
    return np.asarray(np.zeros(384), dtype=np.float32)

def fake_matrix(n=3):
    return np.asarray(np.zeros((n, 384)), dtype=np.float32)

def fake_tensor():
    return np.zeros((384,), dtype=np.float32)

# actual sample from validated runtime df - complete set for reference to pass pydantic construct in question factory 
FR_SAMPLE = {
    'master_id': '19uQRxUh',
    'question_source': 'legacy',
    'original_question_id': 136,
    'syn_id': None,
    'question_type': 'FR',
    'answer_type': 'text',
    'question': 'What is the antidote to Swelling Solution?',
    'answer': 'deflating draught',
    'answer_variations': ['deflating draught', 'draught of deflation'],
    'hint_1': 'This potion is designed to reverse the effects of another common, often mischievous, concoction.',
    'hint_2': 'If something has been made to grow unnaturally large, this potion can return it to its normal size.',
    'hint_3': "It's the perfect counter for an enchantment that causes objects or body parts to expand.",
    'explanation': 'The Deflating Draught is a potent antidote specifically formulated to counteract the effects of the Swelling Solution, which causes rapid and often grotesque enlargement of objects or body parts.',
    'semantic_entity_refs': ['shrinking potion'], # changed for test. original = ['Deflating Draught']
    'semantic_lore_concepts': ['Antidote potion', 'Swelling Solution counter'],
    'source_reference': None,
    'source_quote': None,
    'question_length': 7,
    'answer_length': 2,
    'mcq_options': None,
    'question_tokens': ['what', 'be', 'antidote', 'swell', 'solution'],
    'answer_tokens': ['deflate', 'draught'],
    'combined_unique_tokens': ['what','be','antidote','swell','solution','deflate','draught'],
    'main_keyword': 'what',
    # embeddings
    "question_embeddings": fake_embedding(),
    "answer_embeddings": fake_embedding(),
    "answer_variations_embeddings": fake_matrix(1),
    "mcq_distractors_embeddings":  fake_matrix(3),
    # hydrated runtime tensors
    "question_embeddings_tensor": np.zeros(384, dtype=np.float32),
    "answer_embeddings_tensor": np.zeros(384, dtype=np.float32),
    "answer_variations_embeddings_tensor_matrix": np.zeros((1, 384), dtype=np.float32),
    "mcq_distractors_embeddings_tensor_matrix": np.zeros((3, 384), dtype=np.float32)
    }

def make_fr_question(**overrides):
    """Construct Question object from test sample"""
    payload = copy.deepcopy(FR_SAMPLE)
    payload.update(overrides)
    return question_factory(payload, mode="dev")

# mock sbert checks
def mock_check_semantic_variations(player_tensor, gold_tensor, variation_tensor):
    """return mock correct score + matched variation bool"""
    return 0.92, True   

## happy path: PASS: tier 1 (exact match)
def test_fr_evaluator_with_correct_exact_player_answer():
    """
    The player answer should be evaluated as correct 
    as tier-1 exact match.
    """
    correct_q = make_fr_question()
    player_answer = correct_q.answer
    
    test_result = check_fr_answer(player_answer, correct_q)
    
    assert test_result.is_correct == True
    assert test_result.resolution_tier == 'fr_exact'

## happy path: PASS: tier 2 (fuzzy match)
def test_fr_evaluator_with_correct_fuzzy_player_answer():
    """Minor spelling mistakes should pass Tier-2 fuzzy matching."""

    correct_q = make_fr_question()
    player_answer = 'deflating draft'
    
    test_result = check_fr_answer(player_answer, correct_q)
    
    assert test_result.is_correct == True
    assert test_result.resolution_tier == 'fr_fuzzy'

## happy path: PASS: tier 3, path B (primary SBERT check)
@patch(SBERT_PATH, side_effect=mock_check_semantic_variations)
def test_fr_evaluator_with_semantically_similar_answer(mock_fn):
    """player answer is semantically similar enough to pass semantic SBERT tier."""
    correct_q = make_fr_question()
    player_answer = "drink of deflation"

    test_result = check_fr_answer(player_answer, correct_q)

    mock_fn.assert_called_once()
    assert test_result.is_correct == True
    assert test_result.resolution_tier == "fr_passed_primary_semantic"

## happy path: PASS: tier 3, path C (Ambiguous answer with score boost)
@patch(SBERT_PATH)
def test_fr_evaluator_with_semantically_ambiguous_answer(mock_fn):
    """player answer is semantically similar enough to pass semantic SBERT tier."""
    
    correct_q = make_fr_question()
    # match entity ref for score boost
    player_answer = correct_q.semantic_entity_refs[0]
    # below semantic threshold, above ambiguous floor
    mock_fn.return_value = (0.75, False)

    test_result = check_fr_answer(player_answer, correct_q)

    mock_fn.assert_called_once()
    assert test_result.is_correct == True
    assert test_result.resolution_tier == "fr_passed_semantic_boosted"

## happy path: FAIL: tier 3, path D (incorrect answer below ambiguous threshold)
@patch(SBERT_PATH)
def test_fr_evaluator_with_incorrect_answer(mock_fn):
    """An incorrect answer will fail primary semantic check"""
    
    correct_q = make_fr_question()
    player_answer = "wrong answer"
    mock_fn.return_value = (0.35, False)

    test_result = check_fr_answer(player_answer, correct_q)

    mock_fn.assert_called_once()
    assert test_result.is_correct == False
    assert test_result.resolution_tier == "fr_failed_primary_semantic"

## happy path: PASS: tier 3, path A (outler LLM escalation)
@patch(LLM_PATH)
def test_fr_evaluator_with_correct_verbose_player_answer(mock_llm):
    """The LLM judge will pass the verbose, correct answer"""
    
    # Arrange
    correct_q = make_fr_question()
    player_answer = "I think the correct answer here is a deflating draught"  # wc > 6
    # setup LLMJudgeResponse dto as patch response
    fake_llm_response = Mock()
    fake_llm_response.is_correct = True
    fake_llm_response.quiz_host_response = "Correct."
    fake_llm_response.evaluation_reasoning = "Player demonstrated sufficient conceptual understanding."
    
    # mock return from the LLM call
    mock_llm.return_value= (fake_llm_response, "gemini-3.0-flash", 1.24,True)
   
    # Act
    test_result = check_fr_answer(player_answer, correct_q)
    
    mock_llm.assert_called_once()
    assert test_result.is_correct is True
    assert test_result.resolution_tier == "fr_llm_judge_pass"
    assert test_result.llm_model_used == "gemini-3.0-flash"

## happy path: FAIL: tier 3, path A (outlier LLM escalation)
@patch(LLM_PATH)
def test_fr_evaluator_with_incorrect_verbose_player_answer(mock_llm):
    """The LLM judge will fail the verbose, incorrect answer"""
    
    # Arrange
    correct_q = make_fr_question()
    player_answer = "I think the correct answer here is the lucky potion?"  # wc > 6
    # setup LLMJudgeResponse dto as patch response
    fake_llm_response = Mock()
    fake_llm_response.is_correct = False
    fake_llm_response.quiz_host_response = "Incorrect."
    fake_llm_response.evaluation_reasoning = "Player demonstrated insufficient conceptual understanding."
    
    # mock return from the LLM call
    mock_llm.return_value= (fake_llm_response, "gemini-3.0-flash", 1.40,True)
   
    # Act
    test_result = check_fr_answer(player_answer, correct_q)
    
    mock_llm.assert_called_once()
    assert test_result.is_correct is False
    assert test_result.resolution_tier == "fr_llm_judge_fail"
    assert test_result.llm_model_used == "gemini-3.0-flash"

## Missing gold_tensor
def test_fr_evaluator_missing_gold_tensor():
    """A missing gold answer tensor will raise an error"""
    q = make_fr_question()
    player_answer = q.answer
    q.answer_embeddings_tensor= None

    with pytest.raises(RuntimeError, match= f"Missing answer tensor"):
        check_fr_answer(player_answer, q)
        
## Missing answer variations tensor matrix
def test_fr_evaluator_missing_answer_variation_tensor_matrix():
    """A missing gold answer tensor will raise an error"""
    q = make_fr_question()
    player_answer = q.answer
    q.answer_variations_embeddings_tensor_matrix= None

    with pytest.raises(RuntimeError, match= "Missing variations matrix"):
        check_fr_answer(player_answer, q)                

## Player answer not str (represent missing normalization)
def test_fr_evaluator_player_answer_is_bool():
    """
    A player answer, not a string, will raise an error.
    Light check to check if normalization was done.
    """
    q = make_fr_question()
    player_answer = True
    
    with pytest.raises(TypeError, match="player_answer must be a normalized string"):
        check_fr_answer(player_answer, q)  # type:ignore - wrong dtype used for test intentionally
        