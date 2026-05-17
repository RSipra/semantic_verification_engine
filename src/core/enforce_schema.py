"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) -> Dataset Validation with Pydantic models

-----------------------------------------------------------------------
Shared validation module used across offline pipelines and
runtime evaluation workflows.

This module provides a unified interface for enforcing Pydantic-based
schema validation over question datasets stored in parquet or loaded
into runtime memory.

Core responsibilities:
---------------------
- Resolve schema mappings via runtime or validation registries
- Enforce Pydantic validation on raw or semi-processed DataFrames
- Partition data into validated and flagged records
- Provide deterministic validation behavior across environments

Pipeline usage:
--------------
Offline (generation / validation pipeline): enforce_schema before data-tier 
     DataFrame
        → enforce_schema (structural validation gate)
        → validated DataFrame
        → branching:
            Path A — Promotion / downstream processing
                → enrichment / feature engineering / further pipeline logic
            Path B — Storage (canonical dataset)
                → normalization + serialization
                → pyarrow Table
                → parquet write

Runtime (execution):
    parquet → pyarrow Table → DataFrame → enforce_schema → validated dataset

Design principles:
------------------
- Registry-driven schema resolution (no hardcoded models in logic)
- Pydantic-first validation (strict contract enforcement)
- Environment-agnostic (offline + runtime parity)
- Fail-safe: invalid records are isolated, not silently dropped

"""
from typing import Tuple, Dict, Optional, Type, Literal
import logging
import pandas as pd
import numpy as np
from pydantic import BaseModel, ValidationError

from core.constants import QuestionSource, QuestionType
from core.models import VALIDATION_REGISTRY, RUNTIME_REGISTRY, DataTier

logger = logging.getLogger(__name__)

## Router helpers

def get_validation_scheme(question_source: QuestionSource, data_tier: DataTier) -> dict:
    """Routes to the correct schema map from VALIDATION_REGISTRY."""
    return VALIDATION_REGISTRY.get(question_source, {}).get(data_tier, {})

def get_runtime_scheme(mode: str) -> dict:
    """Routes to the correct schema map from RUNTIME_REGISTRY."""
    scheme = RUNTIME_REGISTRY.get(mode)
    if scheme is None:
        raise ValueError(f"Unknown runtime mode '{mode}'. Expected one of: {list(RUNTIME_REGISTRY.keys())}")
    return scheme

def get_scheme(mode: Optional[str] = None,
               source: Optional[QuestionSource] = None,
               tier: Optional[DataTier] = None) -> dict:
    """
    Return mappings of QuestionType → Pydantic model classes 
    from either runtimve or validation registry
    """
    if mode is not None:
        return get_runtime_scheme(mode)

    if source is not None and tier is not None:
        return get_validation_scheme(source, tier)
        
    raise ValueError("Invalid scheme request")

## Pydantic validators

def validate_record(record: dict,scheme: Dict[QuestionType, Type[BaseModel]], question_type: QuestionType
                    ) -> tuple[BaseModel, str]:
    """Validates a single record against a pre-resolved Pydantic schema map."""
    pydantic_scheme = scheme.get(question_type)
    if pydantic_scheme is None:
        raise ValueError(f"No schema found for {question_type}")

    model_name = pydantic_scheme.__name__
    valid_record = pydantic_scheme(**record)
    return (valid_record, model_name)

def enforce_schema(scheme: Dict[QuestionType, Type[BaseModel]],
                   df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Enforces Pydantic schema validation over a dataset using a pre-resolved
    QuestionType → Pydantic model mapping.

    This function acts as a lightweight validation gate between raw (or
    semi-processed) dataset inputs and downstream pipeline components.

    It assumes that:
    - The input DataFrame originates from a trusted ingestion layer (e.g. parquet load)
    - The schema routing has already been resolved externally via registry helpers
    - Each record contains a valid `question_type` field compatible with `QuestionType`

    Processing Flow:
    ----------------
    1. Normalize input DataFrame (NaN → None conversion)
    2. Iterate over each record
    3. Resolve QuestionType from record metadata
    4. Validate record against corresponding Pydantic model
    5. Partition results into:
       - validated records (schema-compliant)
       - flagged records (validation failures or routing errors)

    Failure Modes Handled:
    ----------------------
    - Pydantic ValidationError → record is captured in flagged output
    - Missing schema mapping (ValueError) → record is flagged with routing error
    - Missing or invalid question_type → record is flagged or skipped safely

    Args:
        scheme (dict):
            Pre-resolved mapping of QuestionType → Pydantic model classes.
            Typically sourced from validation or runtime registry.
        df (pd.DataFrame):
            Input dataset containing raw or semi-structured question records.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]:
            validated_df:
                All records that successfully passed Pydantic validation.
            flagged_df:
                Records that failed validation or schema resolution,
                enriched with error metadata for downstream inspection.

    Notes:
    ------
    - This function is registry-agnostic by design (no direct dependency on
      VALIDATION_REGISTRY or RUNTIME_REGISTRY).
    - Intended for reuse across both offline (batch) and runtime pipelines.
    - Keeps validation deterministic and side-effect free.
    """

    df_clean = df.copy().replace({np.nan: None})
    validated_records, flagged_records = [], []

    for index, record in enumerate(df_clean.to_dict("records")):
        q_id = record.get("temp_qid") or record.get("original_question_id") or f"Row_{index}"

        try:
            q_type = QuestionType(record["question_type"])
            
            valid_record, model_name = validate_record(record, scheme, q_type)
            validated_records.append(valid_record.model_dump())

        except (ValidationError, ValueError) as e:
            logger.warning("Schema validation failed",
                extra={"question_id": q_id,"error_type": type(e).__name__,"error_msg": str(e)})
        
            flagged_records.append({**record,
                                    "error_type": type(e).__name__,
                                    "error_msg": str(e),
                                    "question_id": q_id
                                })

    logger.info("Schema enforcement completed",
        extra={"validated": len(validated_records),"flagged": len(flagged_records)})

    return (pd.DataFrame(validated_records), pd.DataFrame(flagged_records))

# convenience wrapper
def enforce_schema_pipeline(df: pd.DataFrame,
                            mode: Optional[str] = None,
                            source: Optional[QuestionSource] = None,
                            tier: Optional[DataTier] = None
                            )->Tuple[pd.DataFrame, pd.DataFrame]:
    """convenience wrapper to select get scheme and enforce it in one step"""
    scheme = get_scheme(mode=mode, source=source, tier=tier)
    return enforce_schema(scheme, df)
