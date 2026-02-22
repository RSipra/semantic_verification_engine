"""
Project: SVE (ref implementation: Harry Potter Trivia)
QA and Validation logic for Tracer dataset
"""
import string
from typing import Tuple, Optional
import warnings
import unicodedata
import pandas as pd
from pydantic import ValidationError
import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch
import networkx as nx

from ds_utils.ds_constants import QuestionType, QuestionSource, DataTier
import core.models as pyd

## Configuration
SBERT_MODEL_NAME = "all-MiniLM-L6-v2"

### General Helpers (shared across stages)
        

### --- STAGE 1: STRUCTURE ----

## step 1.1. Schema Checks with Pydantic V2
# Gatekeepr - ensure correct quality of data is processed further

# helper for retriveing schema from Pydantic model module
def select_pydantic_scheme(question_source: QuestionSource,
                           data_tier: DataTier) -> dict:
    """
    Retrieves the specific QuestionType-to-Model mapping for a given pipeline branch.

    This helper acts as a router for the central VALIDATION_REGISTRY, allowing 
    the processing engine to fetch the correct schema definitions based on the 
    data's origin (Source) and its current stage in the Medallion Architecture (Tier).

    Args:
        question_source (QuestionSource): The origin of the data (e.g., LEGACY, SYNTHETIC).
        data_tier (DataTier): The maturity level of the data (e.g., BRONZE, SILVER, GOLD).

    Returns:
        dict: A dictionary mapping QuestionType enums to their corresponding 
              Pydantic model classes. Returns an empty dict if no mapping exists.
    """
    model_map = pyd.VALIDATION_REGISTRY.get(question_source,{}).get(data_tier,{})
    return model_map

def validate_record(record: dict, scheme: dict, question_type: QuestionType) -> Tuple:
    """
    Validates a record against a Pydantic schema.
    """
    pydantic_scheme = scheme.get(question_type)
    if pydantic_scheme is None:
        raise ValueError(f"No schema found for {question_type}")

    model_name = pydantic_scheme.__name__
    valid_record = pydantic_scheme(**record)
    return (valid_record, model_name)

# Perform pydantic check on the dataset
def enforce_schema(question_source: QuestionSource,
                   data_tier: DataTier,
                   df: pd.DataFrame):
    """
    Processes a DataFrame through Pydantic schemas.
    Returns a tuple of (validated_df, flagged_df).
    """
    # 1. retrieve the right schema using helper
    scheme = select_pydantic_scheme(question_source, data_tier)
    # 2. Pre-process: Replace NaN with None (on a copy to avoid mutating input)
    df_clean = df.copy().replace({np.nan: None})

    # 3. iterate through df:
    validated_records = []
    flagged_records = []

    # Reminder: change to `itertuples` for non-Tracer scope
    for index, record in enumerate(df_clean.to_dict('records')):  
        q_id = record.get('temp_qid') or record.get('original_question_id') or f"Row_{index}"

        # 4. Check the record
        try:
            q_type = QuestionType(record['question_type'])
            valid_record, model_name = validate_record(record, scheme, q_type)
            # print(f"DEBUG: Validating {q_id} [{question_source.value}] using {model_name} ({q_type.value})")
            validated_records.append(valid_record.model_dump())  # Convert to dict
        
        except ValidationError as e:
            print(f"Skipping record {q_id}: {e}")
            flagged_record = record.copy()
            flagged_record['validation_error'] = str(e)
            flagged_records.append(flagged_record)
    
    print(f"TRACER RESULTS: {len(validated_records)} validated, {len(flagged_records)} flagged")

    return (pd.DataFrame(validated_records), pd.DataFrame(flagged_records))

## step 1.2. Normalization & Preprocessing

# helper to stripping white spaces
def _remove_whitespace(text: str) -> str:
    """strip leading / trailing whitespaces"""
    return text.strip()

# helper for changing all text to lower case
def _to_lower(text: str) -> str:
    """convert str to lower case"""
    return text.lower()

# helper to remove punctuation
def _remove_punctuation(text: str) -> str:
    """Remove punctuation from str"""
    # 3rd agrument in make trans -> what is removed.
    # empty arguments 1, 2, mean string stays same,
    translator = str.maketrans('','', string.punctuation)
    return text.translate(translator)

# helper
def _normalize_unicode(text:str)-> str:
    """Normalize special characters to the same format"""
    return unicodedata.normalize("NFKC", text)

# orchestrator
def normalize_value(value):
    """Takes a column and applies normalization steps to all values"""

    normalization_stages = [
        _normalize_unicode,
        _remove_whitespace,
        _to_lower,
        # NOTE: Punctuation intentionally kept for SBERT
    ]
    # internal helper to loop through normalization stages
    def _apply_stages(s: Optional[str]) -> Optional[str]:
        """sequentially apply methods in stages"""
        # incase the list of stages is empty
        if s is None or s=="":
            warnings.warn("No normalization applied: value is None",  stacklevel=2)
            return None
        for stage in normalization_stages:
            s = stage(s)
        return s
    
    # if value is text, apply directly
    if isinstance(value, str):
        return _apply_stages(value)
    # if value is a list of text, iterate through list values
    elif isinstance(value, (list, np.ndarray)):
        return [_apply_stages(v) for v in value if v is not None]
    # if not str, list(str), simply return value
    return value

### --- STAGE 2: DEDUPLICATION----

# create embeddings for column
def generate_embeddings(dataframe: pd.DataFrame, columns: list, model: SentenceTransformer):
    """Generates embeddings dynamically, trusting Pydantic upstream validation."""
    df = dataframe.copy()

    for col in columns:
        first_element = df[col].iloc[0]

        # 1. handle single strings columns (e.g., 'answer')
        if isinstance(first_element, str):
            col_name = f"{col}_embeddings"
            # encode string to embedding then convert resultign NumPy array -> List[float]
            # this is to make sure df can be saved as Parquet
            df[col_name] = df[col].apply(
                lambda x: model.encode(x).tolist() if pd.notna(x) else None
                )

        # 2. handle columns with lists of strings (e.g. 'answer_variations')   
        elif isinstance(first_element, list):
            col_name = f"{col}_embeddings"
            df[col_name] = df[col].apply(
                # iterate through the list, encoding each string individually as a List[Float].
                # them combines all embeddings in a list -> List[List[float]] for Parquet and Pydantic
                lambda lst: [model.encode(item).tolist() for item in lst]
                if isinstance(lst, list) else None
            )
    return df

## step 2.1: cross-type deduplication

hierarchy_map = {'EX': 1, 'MCQ': 2, 'FR': 3}

def generate_graph_clusters(qids: list, sq_score_df: pd.DataFrame):
            """  """
            # 1. build graph using source_quote similarity score df
            G = nx.from_pandas_edgelist(
                sq_score_df,
                source='qids_rows',
                target='qids_cols',
                edge_attr=True # Automatically adds sq_score, ques_score, ans_score to edge
                )
            
            # 2. add all batch nodes
            G.add_nodes_from(qids)
            
            # 3. extract source quote duplicate clusters
            duplicate_groups = [list(dg) for dg in nx.connected_components(G) if len(dg) > 1]
            
            return duplicate_groups, G

def transform_cluster_to_df():
    """ """
    

def map_ques_type_hierarchy(map: dict, df:pd.DataFrame):
    """"""


    
def analyze_qa_within_group(thres_ans: float, thres_ques:float, ):
    """"""

def group_duplicates(df: pd.DataFrame,
                     id_col_name:'str', 
                     batch_sim_matrix,
                     threshold_sq: float, 
                     threshold_ans: float,
                     threshold_ques: float):
    """"
    """
    for batch in batch_sim_matrix:
        
        batch_data = batch_sim_matrix[batch]
        # unpack dict for batch
        qids, sq_mat, ques_mat, ans_mat = (
            batch_data['batch_qids'],
            batch_data['source_quote_embeddings_sim_matrix'],
            batch_data['question_embeddings_sim_matrix'],
            batch_data['answer_embeddings_sim_matrix']
        )
    
        # 1. FIRST PASS: create duplicate groups based on source quote 
        # 1.1. creates a boolean matrix of all pairs that pass threshold
        rows, cols = np.where(np.triu(sq_mat > threshold_sq, k=1))
        
        # 1.2. keep actual similarity score values as a signal along with coords.
        qids_array = np.array(qids)
        sq_score_df = pd.DataFrame({
            'qids_rows'  : qids_array[rows].tolist(), 
            'qids_cols'  : qids_array[cols].tolist(),
            'sq_score'   : sq_mat[rows, cols],
            'ques_score' : ques_mat[rows, cols],
            'ans_score'  : ans_mat[rows, cols]
        })
        
        # 1.3 create graph cluster from the pairwise comparison
        duplicate_groups, G = generate_graph_clusters(qids, sq_score_df)
