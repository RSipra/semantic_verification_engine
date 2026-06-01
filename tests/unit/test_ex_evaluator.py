"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for the EX Semantic Evaluator
-----------------------------------------------------------------------
EX EVALUATOR — CONTRACT TEST SUITE

Validates tiered MCQ evaluation logic under runtime conditions.

Evaluation pipeline:
- Tier 1/2: O(1) Exact and Fuzzy string matching.
- Tier 3.1: SBERT vector similarity (filters vocabulary mismatches, features Verbosity Bypass).
            Verbose players are directly sent to LLM.
- Tier 3.2: NLI Cross-Encoder (gates inverted logic and contradictions) -> disabled in tracer build.
- Tier 4: LLM Judge escalation for the ambiguous region (vague abstractions/deep lore).

Tests assume fully hydrated runtime question objects (EX),
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
from engine.evaluators.ex_evaluator import check_ex_answer
from game_app.warmup import question_factory

## fixtures

LLM_PATH = "engine.evaluators.ex_evaluator.call_llm_judge"
SBERT_PATH = "engine.evaluators.ex_evaluator.check_semantic_variations"

# actual sample question from runtime tracer dataset (ProductionMCQ_Green)
def fake_embedding():
    return np.asarray(np.zeros(384), dtype=np.float32)

def fake_matrix(n=3):
    return np.asarray(np.zeros((n, 384)), dtype=np.float32)

def fake_tensor():
    return np.zeros((384,), dtype=np.float32)

# actual sample from validated runtime df - complete set for reference to pass pydantic construct in question factory 
EX_SAMPLE = {
    'master_id': 'KRIw02wv',
    'question_type': 'EX',
    'question_source': 'legacy',
    'question': "At the beginning of Harry Potter and the Prisoner of Azkaban, where is Hedwig waiting for Harry after he flees the Dursleys' house?",
    'answer': 'in his room at the leaky cauldron',
    'answer_variations': ["hedwig is waiting in harry's room at the magical inn he stays at before returning to hogwarts.",
    "hedwig is in harry's room at the leaky cauldron.",
    "harry's room, leaky cauldron, wizarding inn, waiting"],
    'mcq_options': None,
    'hint_1': "Think about where Harry goes immediately after leaving his relatives' home.",
    'hint_2': 'This is a secret wizarding inn that serves as a gateway to Diagon Alley.',
    'hint_3': 'The location provides a safe haven for young wizards and is often a first stop when coming to London from the Muggle world.',
    'explanation': 'After Harry accidentally inflates Aunt Marge and flees Privet Drive, he is picked up by the Knight Bus and taken to the Leaky Cauldron. The Ministry of Magic decides not to punish him, and he spends the remainder of his summer there. Hedwig is waiting for him in his assigned room.',
    'semantic_entity_refs': ['Leaky Cauldron', "Harry Potter's room"],
    'semantic_lore_concepts': ['Wizarding inn',
    'Temporary refuge',
    'Diagon Alley access'],
    'original_question_id': 1179,
    'syn_id': None,
    'source_reference': None,
    'source_quote': None,
    'question_length': 23,
    'answer_length': 7,
    'answer_type': 'text',
    'question_tokens': ['beginning','harry','potter','prisoner','azkaban','where','be','hedwig','wait','flee','dursleys','house'],
    'answer_tokens': ['room', 'leaky', 'cauldron'],
    'combined_unique_tokens': ['beginning','harry','potter','prisoner','azkaban','where','be','hedwig','wait','flee','dursleys','house','room','leaky','cauldron'],
    'main_keyword': 'where',
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

def make_ex_question(**overrides):
    """Construct Question object from test sample"""
    payload = copy.deepcopy(EX_SAMPLE)
    payload.update(overrides)
    return question_factory(payload, mode="dev")

# mock sbert checks
def mock_check_semantic_variations(player_tensor, gold_tensor, variation_tensor):
    """return mock correct score + matched variation bool"""
    return 0.92, True 

## happy path: PASS: tier 1 (exact match)
def test_ex_evaluator_with_correct_exact_player_answer():
    """
    The player answer should be evaluated as correct 
    as tier-1 exact match.
    """
    correct_q = make_ex_question()
    player_answer = correct_q.answer
    
    test_result = check_ex_answer(player_answer, correct_q)
    
    assert test_result.is_correct is True
    assert test_result.resolution_tier == 'ex_exact'

## happy path: PASS: tier 2 (fuzzy match)
def test_ex_evaluator_with_correct_fuzzy_player_answer():
    """Minor spelling mistakes should pass Tier-2 fuzzy matching."""

    correct_q = make_ex_question()
    player_answer = 'in his room at the leeky cauldroun'

    test_result = check_ex_answer(player_answer, correct_q)

    assert test_result.is_correct is True
    assert test_result.resolution_tier == 'ex_fuzzy'

## happy path: FAIL: tier 3 (SBERT rejects clearly incorrect answer)
@patch(SBERT_PATH)
def test_ex_evaluator_with_incorrect_answer(mock_sbert):
    """An incorrect answer will fail primary semantic check"""
    
    correct_q = make_ex_question()
    player_answer = "wrong answer"
    mock_sbert.return_value = (0.35, False)

    test_result = check_ex_answer(player_answer, correct_q)

    mock_sbert.assert_called_once()
    assert test_result.is_correct == False
    assert test_result.resolution_tier == "ex_primary_semantic_fail"

## happy path: PASS: tier 4 (LLM pass with correct answer)

@patch(SBERT_PATH)
@patch(LLM_PATH)
def test_ex_evaluator_with_ambiguous_correct_answer(mock_llm, mock_sbert):
    """The LLM judge will pass correct answer"""

    correct_q = make_ex_question()
    player_answer = 'at leaky cauldron, diagon alley, in his room' 
    # mock sbert response: score above ambiguous floor to avoid fast fail
    mock_sbert.return_value = (0.55, False)  
    # setup LLMJudgeResponse dto as patch response
    fake_llm_response = Mock()
    fake_llm_response.is_correct = True
    fake_llm_response.quiz_host_response = "Correct."
    fake_llm_response.evaluation_reasoning = "Player demonstrated sufficient conceptual understanding."
    
    # mock return from the LLM call
    mock_llm.return_value= (fake_llm_response, "gemini-3.0-flash", 1.24,True)
   
    # Act
    test_result = check_ex_answer(player_answer, correct_q)
    
    mock_llm.assert_called_once()
    assert test_result.is_correct is True
    assert test_result.resolution_tier == "ex_llm_judge_pass"
    assert test_result.llm_model_used == "gemini-3.0-flash"

## happy path: FAIL: tier 4 (LLM rejects with incorrect answer)

@patch(SBERT_PATH)
@patch(LLM_PATH)
def test_ex_evaluator_with_ambiguous_incorrect_answer(config, mock_llm, mock_sbert):
    """The LLM judge will fail incorrect answer"""

    correct_q = make_ex_question()
    player_answer = 'at leaky cauldron, diagon alley, in his room' 
    # mock sbert response: score above ambiguous floor to avoid fast fail
    mock_sbert.return_value = (config.ambiguous_answer_floor + 0.01, False)  
    # setup LLMJudgeResponse dto as patch response
    fake_llm_response = Mock()
    fake_llm_response.is_correct = False
    fake_llm_response.quiz_host_response = "Incorrect."
    fake_llm_response.evaluation_reasoning = "Player demonstrated insufficient conceptual understanding."
    
    # mock return from the LLM call
    mock_llm.return_value= (fake_llm_response, "gemini-3.0-flash", 1.24,True) # True = LLM call was successful
   
    # Act
    test_result = check_ex_answer(player_answer, correct_q)
    
    mock_sbert.assert_called_once()
    mock_llm.assert_called_once()
    assert test_result.is_correct is False
    assert test_result.resolution_tier == "ex_llm_judge_fail"
    assert test_result.llm_model_used == "gemini-3.0-flash"

## happy path: PASS: tier 4 (verbose bypass: correct player player answer)

@patch(LLM_PATH)
def test_ex_evaluator_with_correct_verbose_player_answer(mock_llm):
    """Player answer will be bypassed directly to LLM and evaluated correct"""
    
    correct_q = make_ex_question()
    # for bypass: verbose player answer wc > 2*answer wc = 14
    player_answer = 'This was in the third book! he went to the leaky cauldron, diagon alley and found hedwig in his room.'  
    # setup LLMJudgeResponse dto as patch response
    fake_llm_response = Mock()
    fake_llm_response.is_correct = True
    fake_llm_response.quiz_host_response = "Correct."
    fake_llm_response.evaluation_reasoning = "Player demonstrated sufficient conceptual understanding." 
    
    mock_llm.return_value= (fake_llm_response, "gemini-3.0-flash", 1.24, True)
    
    test_result = check_ex_answer(player_answer, correct_q)
    
    mock_llm.assert_called_once()
    assert test_result.is_correct is True
    assert test_result.resolution_tier == "ex_llm_judge_long_ans_pass"
    assert test_result.llm_model_used == "gemini-3.0-flash"
     
## happy path: FAIL: tier 4 (verbose bypass: incorrect player player answer)

@patch(LLM_PATH)
def test_ex_evaluator_with_incorrect_verbose_player_answer(mock_llm):
    """Player answer will be bypassed directly to LLM and evaluated incorrect"""
    
    correct_q = make_ex_question()
    # for bypass: verbose player answer wc > 2*answer wc = 14
    player_answer = 'How did harry even lose Hedwig?! He should take better care and keep her with him at all times!'  
    # setup LLMJudgeResponse dto as patch response
    fake_llm_response = Mock()
    fake_llm_response.is_correct = False
    fake_llm_response.quiz_host_response = "Incorrect."
    fake_llm_response.evaluation_reasoning = "Player didnt answer the question and decided to go on a tangential rant \
                                              about improper animal care." 
    
    mock_llm.return_value= (fake_llm_response, "gemini-3.0-flash", 1.24, True)
    
    test_result = check_ex_answer(player_answer, correct_q)
    
    mock_llm.assert_called_once()
    assert test_result.is_correct is False
    assert test_result.resolution_tier == "ex_llm_judge_long_ans_fail"
    assert test_result.llm_model_used == "gemini-3.0-flash"

## Missing gold_tensor
def test_ex_evaluator_missing_gold_tensor():
    """A missing gold answer tensor will raise an error"""
    q = make_ex_question()
    player_answer = q.answer
    q.answer_embeddings_tensor= None

    with pytest.raises(RuntimeError, match= f"Missing answer tensor"):
        check_ex_answer(player_answer, q)
        
## Missing answer variations tensor matrix
def test_ex_evaluator_missing_answer_variation_tensor_matrix():
    """A missing gold answer tensor will raise an error"""
    q = make_ex_question()
    player_answer = q.answer
    q.answer_variations_embeddings_tensor_matrix= None

    with pytest.raises(RuntimeError, match= "Missing variations matrix"):
        check_ex_answer(player_answer, q)                

## Player answer not str (represent missing normalization)
def test_ex_evaluator_player_answer_is_bool():
    """
    A player answer, not a string, will raise an error.
    Light check to check if normalization was done.
    """
    q = make_ex_question()
    player_answer = True
    
    with pytest.raises(TypeError, match="player_answer must be a normalized string"):
        check_ex_answer(player_answer, q)  # type:ignore - wrong dtype used for test intentionally
