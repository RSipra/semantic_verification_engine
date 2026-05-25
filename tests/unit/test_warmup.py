"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for the Game Warmup orchestrator
-----------------------------------------------------------------------

Tests the session allocation and question hydration layer responsible for:
- deterministic session selection from a validated runtime dataset
- correct conversion of runtime rows into Question objects
- correct session lifecycle behavior (active vs exhausted)

Scope
-----
- row extraction and transformation helpers
- Question object factory correctness
- session allocation logic (warmup orchestrator)

Design boundary
---------------
- Input dataset is already validated and tensor-hydrated upstream (startup layer)
- master_id uniqueness and schema integrity are guaranteed prior to warmup
- warmup does NOT perform dataset validation 

Test scope:
-----------
1. Question Hydration Layer
   - get_question_dict: row → flat dict conversion
   - question_factory: dict → runtime Question object via registry

2. Session Allocation Logic
   - correct session size enforcement
   - correct remaining pool tracking
   - correct exhausted vs active state transitions
   - correct mapping from selected IDs → Question objects

3. Deterministic Behavior (debug contract)
   - same seed produces same session allocation used for
     debugging and reproducibility, not gameplay logic.

4. Failure modes
   - Invalid master_id → ValueError (row extraction layer)
   - Missing question_type → ValueError (factory layer)
   - Invalid enum/question type → ValueError (factory layer)

"""

from doctest import master
from unittest.mock import patch
import pytest
import pandas as pd
import numpy as np

from game_app.warmup import get_question_dict, question_factory, orchestrate_game_warmup
from core.models import RUNTIME_REGISTRY
from core.constants import QuestionType

# patch paths
ROW_DICT = "game_app.warmup.get_question_dict"
Q_FACTORY = "game_app.warmup.question_factory"

Q_OBJECT_MODEL = RUNTIME_REGISTRY["dev"][QuestionType.FR]
RANDOM_SEED = 26
test_sample = {"master_id": "test_warmup",
               "question_type": "FR",
               "answer_type": "text",
               "question": "who is harry potter's best friend?",
               "answer": "ron weasley"}

## Session lifecycle states

# row dict happy path: returns correct dict for df row
def test_get_question_dict_returns_row_dict():
    """Converts a row from the runtime df into a flat dict successfully"""
    df = pd.DataFrame([test_sample])
    master_id = "test_warmup"

    result = get_question_dict(df, master_id)

    assert isinstance(result, dict)
    assert result['master_id'] == "test_warmup"
    # check dict is flat
    assert all(not isinstance(v, dict) for v in result.values())

# Question happy path: correct question objection construction
def test_question_factory_returns_runtime_question_object():
    """Converts row dict  """
    # questions are hydrated into Question runtime objects
    # runtime registry mapping resolves correctly

    row_dict = test_sample.copy()
    expected_model = Q_OBJECT_MODEL

    question = question_factory(row_dict)

    assert question.master_id == "test_warmup"
    assert question.question_type == QuestionType.FR
    assert isinstance(question, expected_model)

# Warmup happy path: returns "active" when enough questions exist
def test_warmup_returns_active_session():
    """warm up successfully returns active session and active status
    when sufficient questions are available in the runtime dataframe"""
    
    session_size = 2
    expected_model = Q_OBJECT_MODEL
    # add an extra row as remaining pool, total 3 rows
    df = pd.DataFrame([test_sample] * (session_size+1)) 
    df['master_id'] = ['test_sample','second_test_sample', 'third_test_sample']

    result = orchestrate_game_warmup(df,RANDOM_SEED, session_size)

    question_ids = [q.master_id for q in result['questions']]

    # status is correct
    assert result['status'] == 'active'
    # session size
    assert len(result['questions']) ==  session_size
    # dtype: List[Question]
    assert isinstance(result['questions'], list)
    assert all(isinstance(q,expected_model) for q in result['questions'])
    # no duplicates within questions
    assert len(question_ids) == len(set(question_ids))
    # remaining pool 
    assert result['remaining_pool']== len(df) - session_size  

# returns "exhausted" when insufficient questions remain
def test_warmup_returns_exhausted_state():
    """warm up sucessfully returns exhausted state when insufficient questions remain"""
    session_size = 2
    df = pd.DataFrame([test_sample])

    result = orchestrate_game_warmup(df,RANDOM_SEED, session_size)

    assert result['status'] == 'exhausted'
    assert result['questions'] is None
    assert result['remaining_pool']== 1

## Deterministic shuffle behavior
# same seed -> same session order
def test_warmup_same_seed_same_order():
    """Same seed should produce identical session allocation order"""

    df = pd.DataFrame([test_sample] * 3) 
    df['master_id'] = ['test_sample','second_test_sample', 'third_test_sample']

    result_1 = orchestrate_game_warmup(runtime_dataframe=df,
                                       random_seed=42,
                                       session_size=3)

    result_2 = orchestrate_game_warmup(runtime_dataframe=df,
                                       random_seed=42,
                                       session_size=3)

    ids_1 = [q.master_id for q in result_1["questions"]]
    ids_2 = [q.master_id for q in result_2["questions"]]

    assert ids_1 == ids_2

## Failure modes
# invalid master_id raises ValueError
def test_get_question_dict_invalid_id_raises():
    """An incorrect master_id raises a ValueError"""
    
    master_id = "non_existent_id"
    df = pd.DataFrame([test_sample])

    with pytest.raises(ValueError) as e:
        get_question_dict(df, master_id)

    assert "master_id  not found in DataFrame" in str(e.value)

# missing question_type raises ValueError
def test_question_factory_missing_question_type_raises():
    """Missing question_type in row dict raises ValueError"""
    row_dict = test_sample.copy()
    del row_dict['question_type']

    with pytest.raises(ValueError) as e:
        question_factory(row_dict)

    assert "CRITICAL: Row missing 'question_type'" in str(e.value)
    
# unregistered QuestionType raises ValueError
def test_question_factory_invalid_type_raises():
    """Unknown question_type raises ValueError"""
    row_dict = test_sample.copy()
    row_dict['question_type'] = "Yes/No"

    with pytest.raises(ValueError) as e:
        question_factory(row_dict)

    assert "CRITICAL: Unrecognized question_type" in str(e.value)
