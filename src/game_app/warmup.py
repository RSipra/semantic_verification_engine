"""_summary_
"""
from pydantic import ValidationError
from core.constants import QuestionType
from core.models import RUNTIME_REGISTRY


## Question object to hold df row data
def get_question_dict(df, target_master_id: str) -> dict:
    """
    Eextracts a single question row from a DataFrame and converts it into 
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
        raise ValueError((f"CRITICAL: Row missing 'questions_type'. \
            Row data: {row_dict.get('master_id', 'Unknown ID')}"))
    
    # 2. convert str from dict to Enum
    try:
        q_type = QuestionType(dict_q_type)
    except ValueError:
        raise ValueError(f"CRITICAL: Unrecognized answer_type '{dict_q_type}'. \
            Must be a valid QuestionType (EX, FR, MCQ).")    
    
    # 3. Look up correct model from the 'runtime registery'
    pydantic_model_class = RUNTIME_REGISTRY[mode].get(q_type)
    if not pydantic_model_class:
        raise ValueError(f"No model registered for type: {q_type}")
    
    # 4gi. create and return the Question object based on question type with row data
    return pydantic_model_class.model_construct(**row_dict)



