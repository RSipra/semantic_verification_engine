"""_summary_
"""

from typing import Any
import random
import logging
import pandas as pd

from core.constants import QuestionType
from core.models import RUNTIME_REGISTRY
from game_app.constants import NUM_QUESTIONS_PER_SESSION

WARMUP_VERSION = "warmup_v1"
logger = logging.getLogger(__name__)

## --- Helpers ---

# Question object to hold df row data
def get_question_dict(df, target_master_id: str) -> dict:
    """
    Extracts a single question row from a DataFrame and converts it into 
    a flat, Pydantic-compatible dictionary.
    This function utilizes Boolean masking to locate the specific question. It intentionally 
    uses `.to_dict('records')[0]` rather than a standard `.to_dict()` to strip away the 
    DataFrame's arbitrary integer index, preventing nested dictionary errors when 
    feeding the output into downstream Pydantic factory models.

    Args:
        df (pd.DataFrame): The source DataFrame (e.g. Gold or Production_Green /_Blue datasets) 
            containing a 'master_id' column.
        target_master_id (str): The unique identifier for the requested question.

    Raises:
        ValueError: If the `target_master_id` does not exist in the provided DataFrame, 
            triggering a loud, fail-fast exception to prevent silent runtime corruption.

    Returns:
        dict: A flat, 1D dictionary of the row's attributes, ready for 
            Pydantic model instantiation
    """
    # 1. create a boolean mask to find the specific row
    row_df = df[df['master_id'] == target_master_id]
    # 2. safety check
    if row_df.empty:
        raise ValueError(f"CRITICAL: master_id '{target_master_id}' not found in DataFrame.")   
    # 3. convert to dict
    row_dict = row_df.to_dict('records')[0]  # for flat dict without index

    return row_dict

# converts a df row into a Question object
def question_factory(row_dict: dict, mode: str = "dev"):
    """
    Hydrates a validated row dictionary into a runtime Question object.

    Assumes upstream runtime validation has already completed during
    warmup/hydration.
    """
    # 1. Identify the question type for row
    dict_q_type = row_dict.get('question_type')

    if dict_q_type is None:
        raise ValueError(("CRITICAL: Row missing 'question_type'. \
            Row data: {row_dict.get('master_id', 'Unknown ID')}"))

    # 2. convert str from dict to Enum
    try:
        q_type = QuestionType(dict_q_type)
    except ValueError as exc:
        raise ValueError(
            f"CRITICAL: Unrecognized question_type '{dict_q_type}'. Must be valid QuestionType."
            ) from exc


    # 3. Look up correct model from the 'runtime registery'
    pydantic_model_class = RUNTIME_REGISTRY[mode].get(q_type)
    if not pydantic_model_class:
        raise ValueError(f"No model registered for type: {q_type}")

    # 4gi. create and return the Question object based on question type with row data
    return pydantic_model_class.model_construct(**row_dict)

## --- Warmup Orchestration ---

def orchestrate_game_warmup(runtime_dataframe: pd.DataFrame,
                            random_seed: int | None,
                            session_size: int = NUM_QUESTIONS_PER_SESSION)-> dict[str,Any]:
    """
    Game warmup sequence: session allocator and question pool manager
    """
    df = runtime_dataframe.copy()
    # convert df to dict using dict comp
    # O(1) row lookup with dict, maintains order for traceability
    row_map = {row['master_id']: row for row in df.to_dict(orient="records")}

    # 1. create shuffled list of questions to create and track session from
    shuffled_master_ids = list(df['master_id'])
    random.Random(random_seed).shuffle(shuffled_master_ids)

    #2. create new session if enough questions remain
    if len(shuffled_master_ids) >= session_size: 

        # pop top N indices for the session (tracer will use 10)
        session_master_ids = [shuffled_master_ids.pop() for _ in range(session_size)]

        # prepare Question objects for a session
        session_questions = [question_factory(row_map[mid]) for mid in session_master_ids]

        logger.info("WARMUP_SESSION_ALLOCATED",
                    extra={"stage": "warmup",
                           "status": "active",
                           "session_size": session_size,
                           "remaining_after": len(shuffled_master_ids),
                           "session_ids": session_master_ids})

        return {"status": "active",
                "questions": session_questions,
                "remaining_pool": len(shuffled_master_ids)}

    # 3. otherwise return "exhausted" flag to controller
    else:
        logger.info("WARMUP_SESSION_EXHAUSTED",
                    extra={"stage": "warmup",
                           "status": "exhausted",
                           "session_size": session_size,
                           "remaining_after": len(shuffled_master_ids)})

        return {"status": "exhausted",
                "questions": None,
                "remaining_pool": len(shuffled_master_ids)}
