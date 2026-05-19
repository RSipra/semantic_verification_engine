"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for the MCQ Semantic Evaluator
-----------------------------------------------------------------------
MCQ EVALUATOR — CONTRACT TEST SUITE

Validates tiered MCQ evaluation logic under runtime conditions.

Evaluation pipeline:
1. Exact match
2. Fuzzy match (edit distance)
3. Semantic similarity (SBERT + distractor margin)

Tests assume fully hydrated runtime question objects (MCQ),
constructed via warmup factory with precomputed embeddings.

Focus:
- correctness of tier routing
- semantic fallback behavior (mocked SBERT layer)
- enforcement of runtime input contracts
- robustness against invalid or missing tensor state   
"""

from unittest.mock import patch
import copy
import pytest
import numpy as np
from engine.evaluators.mcq_evaluator import check_mcq_answer
from game_app.warmup import question_factory

## fixtures
SBERT_PATH = "engine.evaluators.mcq_evaluator.check_semantic_variations"
# actual sample question from runtime tracer dataset (ProductionMCQ_Green)
def fake_embedding():
    return np.asarray(np.zeros(384), dtype=np.float32)

def fake_matrix(n=3):
    return np.asarray(np.zeros((n, 384)), dtype=np.float32)

def fake_tensor():
    return np.zeros((384,), dtype=np.float32)

# actual sample from validated runtime df - complete set for reference to pass pydantic construct in question factory 
MCQ_SAMPLE = {
    'mcq_options': ['incendio maxima','confringo inferno','fiendfyre','ignis maleficus'],
    'question_type': 'MCQ',
    'question_source': 'synthetic',
    'question': 'What extremely dangerous cursed fire spell did Crabbe unleash in the Room of Requirement?',
    'answer': 'fiendfyre',
    'answer_variations': ['fiendfyre'],
    'hint_1': 'This powerful and destructive spell is known to be one of the few things capable of destroying Horcruxes, but it is incredibly difficult to control.',
    'hint_2': 'Hermione recognized this specific dark magic when she saw it, immediately identifying its perilous nature.',
    'hint_3': 'The fire created by this curse is sentient and seeks to destroy all in its path, often taking the form of monstrous flaming creatures.',
    'explanation': 'Crabbe unleashed Fiendfyre in the Room of Requirement, a dark and incredibly dangerous cursed fire spell. This chaotic magic is one of the few known substances powerful enough to destroy Horcruxes, but its sentient and uncontrollable nature makes it exceptionally perilous to cast.',
    'semantic_entity_refs': ['Fiendfyre'],
    'semantic_lore_concepts': ['Cursed fire','Dark magic spell','Horcrux destruction method','Room of Requirement incident'],
    'master_id': 'HyKMnEYj',
    'original_question_id': None,
    'syn_id': 'SYN_036',
    'source_reference': 'deathly_hallows Chapter 31',
    'source_quote': 'It was not normal fire; Crabbe had used a curse of which Harry had no knowledge. ... "It must have been Fiendfyre!" whimpered Hermione, her eyes on the broken piece. "Sorry?" "Fiendfyre ¨C cursed fire ¨C it\'s one of the substances that destroy Horcruxes, but I would never, ever have dared use it, it\'s so dangerous ¨C how did Crabbe know how to ¨C?"',
    'question_length': 14,
    'answer_length': 1,
    'answer_type': 'text',
    'question_tokens': ['what','extremely','dangerous','curse','fire','spell','do','crabbe','unleash','room','requirement'],
    'answer_tokens': ['fiendfyre'],
    'combined_unique_tokens': ['what','extremely','dangerous','curse','fire','spell','do','crabbe','unleash','room','requirement','fiendfyre'],
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

def make_mcq_question(**overrides):
    """Construct Question object from test sample"""
    payload = copy.deepcopy(MCQ_SAMPLE)
    payload.update(overrides)
    return question_factory(payload, mode="dev")

# mock sbert checks
def mock_check_semantic_variations(player_tensor, gold_tensor, variation_tensor):
    """ return mock correct score + matched variation bool"""
    return 0.92, True  

## happy path - tier 1 pass 
def test_mcq_evaluator_with_correct_exact_player_answer():
    """
    The player answer should be evaluated as correct 
    as tier-1 exact match.
    """
    correct_q = make_mcq_question()
    player_answer = correct_q.answer

    test_result = check_mcq_answer(player_answer, correct_q)

    assert test_result.is_correct == True
    assert test_result.resolution_tier == 'mcq_exact'

## happy path - tier 2 pass 

def test_mcq_evaluator_with_correct_fuzzy_player_answer():
    """
    Minor spelling mistakes should pass Tier-2 fuzzy matching.
    """

    correct_q = make_mcq_question()
    player_answer = 'fiendfire'
    
    test_result = check_mcq_answer(player_answer, correct_q)
    
    assert test_result.is_correct == True
    assert test_result.resolution_tier == 'mcq_fuzzy'

## happy path - tier 3 pass
@patch(SBERT_PATH, side_effect=mock_check_semantic_variations)
def test_mcq_evaluator_with_semantically_similar_answer(mock_fn):
    """
    player answer is semantically similar enough to correct ans and 
    distinct enough from distractors and pass semantic SBERT tier.
    """
    correct_q = make_mcq_question()
    player_answer = "friend fire"

    test_result = check_mcq_answer(player_answer, correct_q)

    mock_fn.assert_called_once()
    assert test_result.is_correct == True
    assert test_result.resolution_tier == "mcq_passed_semantic"

##  Incorrect answer: all tiers fail 
@patch(SBERT_PATH)
def test_mcq_evaluator_with_incorrect_answer(mock_fn):
    """An incorrect answer will fail all tiers"""
    
    correct_q = make_mcq_question()
    player_answer = "wrong answer"
    mock_fn.return_value = (0.35, False)

    test_result = check_mcq_answer(player_answer, correct_q)

    mock_fn.assert_called_once()
    assert test_result.is_correct == False
    assert test_result.resolution_tier == "mcq_failed_semantic"

## Missing gold tensor
def test_mcq_evaluator_missing_gold_tensor():
    """A missing gold answer tensor will raise an error"""
    q = make_mcq_question()
    player_answer = 'fiendfire'
    q.answer_embeddings_tensor= None

    with pytest.raises(RuntimeError, match= "Missing answer tensor for Question"):
        check_mcq_answer(player_answer, q)

## Missing answer variations tensor matrix
def test_mcq_evaluator_missing_answer_variation_tensor_matrix():
    """A missing gold answer tensor will raise an error"""
    q = make_mcq_question()
    player_answer = 'fiendfire'
    q.answer_variations_embeddings_tensor_matrix= None

    with pytest.raises(RuntimeError, match= "Missing variations matrix"):
        check_mcq_answer(player_answer, q)

## Player answer not str (represent missing normalization)
def test_mcq_evaluator_player_answer_is_bool():
    """
    A player answer, not a string, will raise an error.
    Light check to check if normalization was done.
    """
    q = make_mcq_question()
    player_answer = True
    
    with pytest.raises(TypeError, match="player_answer must be a normalized string"):
        check_mcq_answer(player_answer, q)  # type:ignore - wrong dtype used for test intentionally
