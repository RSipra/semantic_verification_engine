"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) ->  Application Startup Orchestrator
-----------------------------------------------------------------------
Bootstrap orchestrator that initializes and probes system dependencies,
and assembles a structured runtime snapshot (signals + payload)
for the decision-making game controller.

DESIGN ASSUMPTIONS (Runtime Integrity Model)
--------------------------------------------
- Dataset is validated offline before being packaged into the container.
- Runtime operates on an immutable Parquet artifact (no external writes).
- System is isolated except for LLM API calls.

RUNTIME POLICY
--------------
- Tensor hydration is deterministic.
- Missing or null values in required tensor columns trigger startup failure.
- Missing or null values in optional tensor columns result in row-level quarantine.
- Pydantic validation is applied post-hydration.
- Invalid rows are quarantined (excluded from runtime dataset).

Failure handling:
- Missing required structure → RAISE (startup failure)
- Row-level validation issues → WARN + quarantine

NOTE
----
This tracer assumes controlled, local execution with pre-validated inputs.

"""
import time
from typing import List, Tuple
import logging
import pyarrow.parquet as pq
import pandas as pd
import numpy as np
import torch

from core.enforce_schema import enforce_schema_pipeline
from core.embeddings import get_sbert_model, sbert_settings
from engine.services.llm_service import warmup_llm_connection

STARTUP_MODULE_VERSION = "sup_v1"
logger = logging.getLogger(__name__)

## --- CONSTANTS & CONFIGURATION ---

# local container path for dataset (baked in during Docker build)
DATASET_PATH = "/app/data/tracer_production_green_v1.parquet"

# columns that will be hydrated into tensors
emb_cols = ['question_embeddings', 'answer_embeddings']
emb_list_cols = ['answer_variations_embeddings', 'mcq_distractors_embeddings']

## --- HELPERS ---
# 1. Add tensors for embedding columns
# helper to convert list of arrays into a single 2D tensor,
# handling edge cases for empty/missing data and read-only Parquet arrays
def _to_matrix_tensor(x):
    """
    Handles read-only Parquet arrays and list-of-arrays,
    converting them into a single, writable 2D PyTorch Tensor.
    AI-generated (Google Gemini 3 pro)
    """
    # empty / missing case 
    if x is None or not hasattr(x, '__len__') or len(x) == 0:
        return None
    
    try:
        clean_2d_array = np.stack(x).astype(sbert_settings.numpy_dtype) # Standardized dtype
        return torch.from_numpy(clean_2d_array)
    
    except Exception as e:
        logger.warning("TENSOR_CONVERSION_FAILED",
                       extra={"stage": "startup_tensor_hydration",
                              "error": str(e),
                              "input_type": str(type(x))
                              })
        return None

def _prepare_runtime_tensors(dataframe: pd.DataFrame, 
                            embedding_col_names: List[str], 
                            embedding_list_cols_names: List[str]) -> pd.DataFrame:
    """
    Converts embeddings into PyTorch Tensors to eliminate casting latency at runtime.
    """
    tensor_df = dataframe.copy()

    # 1. Validation
    all_requested = embedding_col_names + embedding_list_cols_names
    missing = [col for col in all_requested if col not in tensor_df.columns]
    if missing:
        logger.error("RUNTIME_DF_MISSING_COLUMNS",
                     extra={"stage": "startup_tensor_hydration",
                            "missing_columns": missing})
        raise ValueError(f"Pipeline Error: Missing columns: {missing}")

    # 2. Cast simple 1D embeddings (question_embeddings, answer_embeddings)
    for col in embedding_col_names:
        col_name = f"{col}_tensor"
        # exlicit dtype conversion to float32 for standaridzed tensor type and reduce memory usage
        tensor_list = [
            torch.from_numpy(np.array(x, dtype=sbert_settings.numpy_dtype)) if x is not None else None 
            for x in tensor_df[col]
        ]
        # Wrap in pd.Series to satisfy Pylance __setitem__ overloads
        tensor_df[col_name] = pd.Series(tensor_list, index=tensor_df.index)

    # 3. Cast 2D list of embeddings matrices 
    # (answer_variations_embeddings, mcq_distractors_embeddings)
    for col in embedding_list_cols_names:
        col_name = f"{col}_tensor_matrix"
        matrix_list = [_to_matrix_tensor(x) for x in tensor_df[col]]
        # Wrap in pd.Series to satisfy Pylance __setitem__ overloads
        tensor_df[col_name] = pd.Series(matrix_list, index=tensor_df.index)

    return tensor_df

## --- STARTUP ORCHESTRATOR ---

def orchestrate_application_startup() ->Tuple[pd.DataFrame, dict]:
    """
    Application Startup Orchestrator (Tracer Build)
    to initialize the runtime environment

    Pipeline Overview:
    ------------------
    1. Loads SBERT singleton embedding model and performs warmup inference
    2. Loads pre-validated parquet dataset from container artifact
    3. Hydrates embedding columns into PyTorch tensor representations
    4. Performs structural integrity checks on hydrated tensor columns
       - Ensures required tensor columns exist
       - Ensures required tensors contain no null values
    5. Applies Pydantic schema enforcement via runtime validation pipeline
       - Valid rows are retained for execution
       - Invalid rows are quarantined and logged
    6. Performs LLM warmup to establish connection latency baseline

    Runtime Integrity Model:
    ------------------------
    - Dataset is assumed to be pre-validated offline before containerization.
    - Runtime assumes immutable input artifact (no external mutation).
    - Validation at startup is limited to structural and hydration integrity checks.
    - Row-level schema violations are quarantined, not treated as fatal errors.

    Contract:
    ---------
    - SBERT + dataset + tensor pipeline must succeed (GO / NO-GO gate)
    - Validation cannot quarantime the whole dataset (runtime_df is empty) (GO / NO-GO gate)
    - LLM warmup is a non-blocking readiness signal
    - Row-level schema issues are quarantined, not fatal

    Returns:
    --------
    runtime_df : pd.DataFrame
        Fully validated runtime dataset (post-quarantine filtering)
    system_signals : dict
        status and latency signal of services for downstream game controller

    TODO:
    -----
    - Refactor tensor hydration into dedicated helper module
    - Extract validation checks into standalone integrity validator
    - Introduce structured StartupResult TypedDict / DTO for cleaner contract
    - Optionally unify warmup + dataset status into single system health object
    - validation should give signal runtime_df is operational sufficient for game session 
      (has enough questions). 

    """
    
    # 1: load sbert singleton embedding model & warmup with dummy inference
    
    t0 = time.time()
    local_model = get_sbert_model()
    try:
        local_model.encode("warmup", show_progress_bar=False)
        sbert_warmup_success = True
    except Exception:
        sbert_warmup_success = False
        logger.exception("SBERT_WARMUP_FAILED")
        raise RuntimeError("SBERT initialization failed")
    
    sbert_init_time = time.time() - t0
    
    # 2. read parquet as pyarrow table, convert to pd.dataframe, validate and hydrate with pydantic model
    try:
        runtime_table = pq.read_table(DATASET_PATH)
    except Exception as e:
        logger.exception("DATA_LOAD_FAILED")
        raise RuntimeError("Dataset load failed") from e
    
    unvalidated_runtime_df = runtime_table.to_pandas()
    
    # 3: hydrate tensors for the entire tracer dataset
    unvalidated_runtime_df = _prepare_runtime_tensors(dataframe=unvalidated_runtime_df,
                                                      embedding_col_names=emb_cols,
                                                      embedding_list_cols_names=emb_list_cols)
    
    # 4. tensor validation post-hydration 
    required_cols = [f"{col}_tensor" for col in emb_cols]
    expected_cols = (required_cols +[f"{col}_tensor_matrix" for col in emb_list_cols])
    
    #  - make sure new tensor columns exist
    # TODO: add controller layer for required column outcome.
    missing_cols = [col for col in expected_cols if col not in unvalidated_runtime_df.columns]
    if missing_cols:
        logger.error("TENSOR_HYDRATION_INCOMPLETE",extra={"stage": "startup",
                                                          "missing_columns": missing_cols})
        raise RuntimeError(f"Tensor hydration failed. Missing columns: {missing_cols}")
    
    #  - make sure required tensor columns are not null (question, answer)
    for col in required_cols:
        if unvalidated_runtime_df[col].isna().any():
            null_count = int(unvalidated_runtime_df[col].isna().sum())
            logger.error("TENSOR_HYDRATION_NULL_VALUES",
                         extra={"stage": "startup",
                                "column": col,
                                "null_count": null_count})
            raise RuntimeError(f"Required tensor column has null values: {col}")
    
    # safety check: make sure all questions in dataset are unique 
    #               eventhough highly unlikely after offline validation
    if unvalidated_runtime_df["master_id"].duplicated().any():
        logger.error("DUPLICATE_MASTER_ID_RUNTIME_DETECTED",
                     extra={
                         "stage": "startup",
                         "duplicate_count": int(unvalidated_runtime_df["master_id"].duplicated().sum())
                         })
        raise RuntimeError("Duplicate master_id detected in runtime dataset")    
    
    # 5. validate with Pyndantic model
    runtime_df, runtime_flagged = enforce_schema_pipeline(df=unvalidated_runtime_df,mode="dev")
    
    # confirm validated df has records (controller will confirm if enough playable questions)
    if runtime_df.empty:
        logger.error("RUNTIME_VALIDATION_FAILED",
                     extra={"stage": "startup",
                            "sample": runtime_flagged[runtime_flagged["error_type"].notna()].head(),
                            "error_type_count": runtime_flagged['error_type'].value_counts(),
                            "error_distribution": runtime_flagged.groupby(["question_type", "error_type"]).size()})
        raise RuntimeError("Validated runtime dataset is empty")
    
    # if runtime_flagged is not empty, log the number of flagged rows and sample master_ids for traceability
    if not runtime_flagged.empty:
        logger.warning("PYDANTIC_RECORDS_FLAGGED", 
                       extra = {"stage":"startup",
                                "flagged_count": len(runtime_flagged),
                                # viewing all during dev, will sample in future
                                "flagged_master_ids": runtime_flagged["master_id"].tolist()}) 
    
    # 6. Initialize game session LLM connection.
    
    # return warmup outcome as capability signal to controller
    # TODO: update soft-failure in LLM service (owns) / controller (handles response)
    # LLM service → produces LLM health (OK / DEGRADED / FAILED) state /
    # Startup → collects system states /
    # Controller → applies game rules to states
    warmup_outcome = warmup_llm_connection()
    # session.log_event("warmup", warmup_outcome)
    
    logger.info("STARTUP_COMPLETE", 
                extra={
                    "stage":"startup",
                    "sbert_warmup_success": sbert_warmup_success,
                    "sbert_model_name": sbert_settings.model_name,
                    "sbert_init_time_sec": sbert_init_time,
                    "runtime_df_count": len(runtime_df),
                    "schema_flag_count": len(runtime_flagged),
                    "llm_warmup_success": warmup_outcome['success'],
                    "model":warmup_outcome['model'],
                    "duration_sec": warmup_outcome['duration_sec']
                })
    # clear system signals for the controller once startup successfully complete
    system_signals = {"sbert": {"status": "OK", "latency": sbert_init_time},
                      "dataset": {"status": "OK"},
                     "tensor": {"status": "OK"},
                     "validation": {"status": "OK"},
                     "llm": warmup_outcome
                     }
    
    # startup status for main to decide to continue to session or buffer
    # hard constraints: required for game to start (LLM is a soft constraint)
    hard_ok = all(
        system_signals[k]["status"] == "OK"
        for k in ["sbert", "dataset", "tensor", "validation"]
    )
    system_signals["startup_ready"] = hard_ok
    
    return runtime_df, system_signals
