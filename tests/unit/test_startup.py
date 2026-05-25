"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for the game application startup
-----------------------------------------------------------------------
Startup Orchestrator Contract Tests

Covers:
- Hard failures (system must NOT start)
  - SBERT initialization failure
  - dataset load failure
  - tensor hydration failures
  - validation elimination of all rows

- Soft failures (system starts with degraded signals)
  - LLM warmup failure/degradation

Contract:
- orchestrate_application_startup() must either:
  1. raise RuntimeError (hard fail path)
  2. return (runtime_df, system_signals)

"""
from unittest import mock
from unittest.mock import patch, Mock
import pytest
import pandas as pd
import numpy as np

from engine.startup import orchestrate_application_startup

# patch paths
SBERT = "engine.startup.get_sbert_model"
DATA = "engine.startup.pq.read_table"
TENSORS = "engine.startup._prepare_runtime_tensors"
VALIDATION = "engine.startup.enforce_schema_pipeline"
LLM_WUP = "engine.startup.warmup_llm_connection"

test_sample = {
    'master_id':'unittest1',
    'question_type':'FR',
    'answer_type':'numeric',
    'question':'who is harrys best friend?',
    'answer':'Ron Weasley',
    'question_embeddings_tensor':np.zeros(384, dtype=np.float32),
    'answer_embeddings_tensor':np.zeros(384, dtype=np.float32),
    'answer_variations_embeddings_tensor_matrix':np.zeros((1, 384), dtype=np.float32),
    'mcq_distractors_embeddings_tensor_matrix':np.zeros((3, 384), dtype=np.float32)   
}

## Happy Path: Successful startup returns correct payload

@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
@patch(VALIDATION)
@patch(LLM_WUP)
def test_startup_returns_correct_payload(mock_llm,  # mocks passed in reverse order to patches
                                         mock_validation,
                                         mock_tensors,
                                         mock_table,
                                         mock_get_sbert_model):
    """
    Happy path: startup returns the correct payload
    -> runtime_df and llm warmup_outcome
    """
    # ---arrange the mocks---

    # SBERT
    # mock the SBERT model object returned by get_sbert_model()
    mock_local_model = Mock()   # represents: local_model
    # mock encode method used for warmup call (success = no exception)
    mock_local_model.encode = Mock()
    # mock get_sbert_model() returns a model object whose encode method can be called without error
    mock_get_sbert_model.return_value = mock_local_model

    # dataframe
    mock_df = pd.DataFrame([test_sample])
    mock_arrow_table = Mock()
    mock_table.return_value = mock_arrow_table
    mock_arrow_table.to_pandas.return_value = mock_df

    # tensor hydration
    mock_tensors.return_value = mock_df

    # pydantic schema validation
    mock_validation.return_value = (mock_df, pd.DataFrame())

    # mock llm call
    mock_llm.return_value = {"success": True,"duration_sec": 0.12,"model": "mock-model"}

    # ---Act ---
    runtime_df, system_signals =  orchestrate_application_startup()

    # ---assert ---
    assert isinstance(runtime_df, pd.DataFrame)
    assert system_signals['llm']["success"] is True
    mock_table.assert_called_once()
    mock_tensors.assert_called_once()
    mock_validation.assert_called_once()
    mock_llm.assert_called_once()

## Hard Failure paths (must raise error)

# SBERT failure
@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
def test_startup_sbert_hard_failure_raises_error(mock_tensors, 
                                                 mock_table, 
                                                 mock_get_sbert_model):
    """
    SBERT failure should block startup immediately.
    """
    # Arrange: SBERT throws on encode
    mock_model = Mock()
    mock_model.encode.side_effect = Exception()
    mock_get_sbert_model.return_value = mock_model

    with pytest.raises(RuntimeError) as e:
        orchestrate_application_startup()

    assert "SBERT initialization failed" in str(e.value)
    mock_get_sbert_model.assert_called_once()
    mock_table.assert_not_called()
    mock_tensors.assert_not_called()

# dataset load failure
@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
def test_startup_dataload_hard_failure_raises_error(mock_tensors, 
                                                    mock_table, 
                                                    mock_get_sbert_model):
    """Failure in loading the parquet dataset will block startup"""
    # pass sbert
    mock_get_sbert_model.return_value = Mock()

    # dataload fails
    mock_table.side_effect = Exception()

    with pytest.raises(RuntimeError) as e:
        orchestrate_application_startup()

    mock_get_sbert_model.assert_called_once()
    assert "Dataset load failed" in str(e.value)
    mock_table.assert_called_once()
    mock_tensors.assert_not_called()  

# Tensor failure (missing col)
@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
@patch(VALIDATION)
def test_startup_tensors_hard_failure_raises_error(mock_validation,
                                                   mock_tensors, 
                                                   mock_table, 
                                                   mock_get_sbert_model):
    """Startup must fail if required tensor columns are missing after hydration """
    # pass sbert
    mock_get_sbert_model.return_value = Mock()
    # pass reading data
    mock_table.return_value.to_pandas.return_value = pd.DataFrame([test_sample])

    valid_df = pd.DataFrame([test_sample])
    # create missing col
    invalid_df = valid_df.drop(columns=["question_embeddings_tensor"])
    # tensor hydration
    mock_tensors.return_value = invalid_df

    with pytest.raises(RuntimeError) as e:
        orchestrate_application_startup()

    mock_get_sbert_model.assert_called_once()
    mock_table.assert_called_once()
    mock_tensors.assert_called_once()
    assert "Tensor hydration failed" in str(e.value)
    mock_validation.assert_not_called()

# Tensor failure (required cols have nulls)
@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
@patch(VALIDATION)
def test_startup_tensors_hard_failure_with_nulls_raises_error(mock_validation,
                                                              mock_tensors, 
                                                              mock_table, 
                                                              mock_get_sbert_model):
    """Startup must fail if required tensor columns have nulls after hydration"""
    # pass sbert
    mock_get_sbert_model.return_value = Mock()
    # pass reading data
    mock_table.return_value.to_pandas.return_value = pd.DataFrame([test_sample])

    df = pd.DataFrame([test_sample])
    # create null required col
    df["question_embeddings_tensor"] = [None]
    # tensor hydration
    mock_tensors.return_value = df

    with pytest.raises(RuntimeError) as e:
        orchestrate_application_startup()

    mock_get_sbert_model.assert_called_once()
    mock_table.assert_called_once()
    mock_tensors.assert_called_once()
    assert "Required tensor column has null values" in str(e.value)
    mock_validation.assert_not_called()
    
# duplicate master ids detected in the dataset
@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
@patch(VALIDATION)
def test_startup_duplicate_master_ids_raises_error(mock_validation,
                                                   mock_tensors,
                                                   mock_table,
                                                   mock_get_sbert_model):
    """Startup must fail during dataset integrity check if duplicate master_ids exist"""
    mock_df = pd.DataFrame([test_sample, test_sample])  # duplicate master_id
    # pass sbert
    mock_get_sbert_model.return_value = Mock()
    # pass reading data
    mock_table.return_value.to_pandas.return_value = mock_df
    # pass tensor hydration
    mock_tensors.return_value = mock_df
    
    with pytest.raises(RuntimeError) as e:
        orchestrate_application_startup()

    mock_get_sbert_model.assert_called_once()
    mock_table.assert_called_once()
    mock_tensors.assert_called_once()
    assert "Duplicate master_id detected" in str(e.value)
    mock_validation.assert_not_called()     

# Pydantic validation returns and empty runtime_df
@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
@patch(VALIDATION)
@patch(LLM_WUP)
def test_startup_validation_fails_all_records_raises_error(mock_llm,
                                                           mock_validation,
                                                           mock_tensors,
                                                           mock_table,
                                                           mock_get_sbert_model):
    """Validation eliminated all usable content, system cannot start"""
    # pass sbert
    mock_get_sbert_model.return_value = Mock()
    # pass reading data
    mock_df = pd.DataFrame([test_sample])
    mock_table.return_value.to_pandas.return_value = mock_df
    # pass tensor
    mock_tensors.return_value = mock_df
     # runtime_df is empty, runtime_flagged quarantines all the cases
    mock_validation.return_value = (pd.DataFrame(),   # runtime_df (empty)
                                    pd.DataFrame(columns=["error_type",
                                                          "question_type", 
                                                          "master_id"]))

    with pytest.raises(RuntimeError) as e:
        orchestrate_application_startup()

    mock_get_sbert_model.assert_called_once()
    mock_table.assert_called_once()
    mock_tensors.assert_called_once()
    mock_validation.assert_called_once()
    assert "Validated runtime dataset is empty" in str(e.value)
    mock_llm.assert_not_called()

## Soft Failure path (flagged for controller)
# LLM failure
@patch(SBERT)
@patch(DATA)
@patch(TENSORS)
@patch(VALIDATION)
@patch(LLM_WUP)
def test_startup_returns_llm_warmup_call_fails(mock_llm, 
                                               mock_validation,
                                               mock_tensors,
                                               mock_table,
                                               mock_get_sbert_model):
    """
    startup returns the correct payload
    -> runtime_df and startup signals with LLM warmup failure signal
    """
    # ---arrange the mocks---

    # SBERT
    mock_get_sbert_model.return_value = Mock()

    # dataframe
    mock_df = pd.DataFrame([test_sample])
    mock_arrow_table = Mock()
    mock_table.return_value = mock_arrow_table
    mock_arrow_table.to_pandas.return_value = mock_df

    # tensor hydration
    mock_tensors.return_value = mock_df

    # pydantic schema validation
    mock_validation.return_value = (mock_df, pd.DataFrame())

    # mock llm call
    mock_llm.return_value = {"success": False,"duration_sec": 0.0,"model": "mock-model"}

    _, system_signals =  orchestrate_application_startup()

    assert isinstance(_, pd.DataFrame)
    assert "llm" in system_signals
    assert isinstance(system_signals["llm"], dict)
    assert system_signals["llm"]["success"] is False
    assert "duration_sec" in system_signals["llm"]
    assert "model" in system_signals["llm"]
    assert system_signals["sbert"]["status"] == "OK"
    assert system_signals["dataset"]["status"] == "OK"
