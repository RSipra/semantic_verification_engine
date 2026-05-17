"""
Project: SVE (ref implementation: Harry Potter Trivia)
QA and Validation logic for Tracer dataset
"""
import string
import math
import types
from typing import Tuple, Optional, List,  get_origin, get_args, Union, Literal
import warnings
import unicodedata
import re
import hashlib
import base64
import json
import pandas as pd
from pydantic import ValidationError
import numpy as np
from sentence_transformers import SentenceTransformer, util
import torch
import networkx as nx
import pyarrow as pa



from core.constants import QuestionType, QuestionSource
from core.models import DataTier
from notebook_support.text_processing import clean_text_fn
import core.models as pyd

## Configuration
SBERT_MODEL_NAME = "all-MiniLM-L6-v2"
# hierarchy of questions within a duplicate group
qtype_hierarchy_map = {'EX': 1, 'MCQ': 2, 'FR': 3}
# composite similarity score for evaluation / comparison of questions within duplicate groups
SIM_WEIGHTS = {'quote': 0.5,'answer': 0.4,'question': 0.1}
SILVER_COMPLEX_COLS = ['generation_prompt_version', 'enrich_audit_flags']
COLS_FOR_EMBEDDINGS = ['question', 'answer', 'source_quote','answer_variations','mcq_distractors']
EMBEDDING_COL_NAMES = ['question_embeddings','answer_embeddings','source_quote_embeddings']

### General Helpers (shared across stages)
        

### --- STAGE 1: STRUCTURE ----

## step 1.1. Schema Checks with Pydantic V2
# Gatekeepr - ensure correct quality of data is processed further

# TODO: update pipeline to use core.enforce_schema.py for pydantic evals.

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

# MCQ only: separate the distrators mcq_options so their embeddings can be calculated separately
def append_text_distractors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a new column 'mcq_distractors' containing a list of string distractors 
    (filtering out the correct answer) for MCQ questions.
    Args:
        df (pd.DataFrame): The dataset containing 'question_type', 'answer', 
            and 'mcq_options'.
    Returns:
        pd.DataFrame: A new dataframe with the added 'mcq_distractors' column 
        formatted as List[str]. Returns None for non-MCQ rows.
    """
    df_transformed = df.copy()

    def get_distractors(row):
        # fast exit for non MCQs or malformed lists
        if row.get('question_type') != 'MCQ' or not isinstance(row.get('mcq_options'), list):
            return None

        # local safety baseline
        correct_ans = str(row.get('answer', '')).strip().lower()
        
        # filter & enforce string type
        return [ str(opt) for opt in row['mcq_options'] if str(opt).strip().lower() != correct_ans]

    # Apply the logic and create the new column
    df_transformed['mcq_distractors'] = df_transformed.apply(get_distractors, axis=1)
    
    return df_transformed

# create embeddings for column
def generate_embeddings(dataframe: pd.DataFrame, columns: list, model: SentenceTransformer):
    """Generates embeddings dynamically, trusting Pydantic upstream validation."""
    df = dataframe.copy()

    for col in columns:
        col_name = f"{col}_embeddings"

        # 1. determine column type based on first non-null value
        first_valid_idx = df[col].first_valid_index()

        # Defensive check: If the entire column is NaN/empty, just make an empty embedding column and skip
        if first_valid_idx is None:
            df[col] = None
            print(f"Warning: Column '{col}' is completely empty. Skipping embeddings.")
            continue

        first_element = df.loc[first_valid_idx, col]

        # 2. handle single strings columns (e.g., 'answer')
        if isinstance(first_element, str):
            # encode string to embedding then convert resultign NumPy array -> List[float]
            # this is to make sure df can be saved as Parquet
            df[col_name] = df[col].apply(
                lambda x: model.encode(x).tolist() if pd.notna(x) else None
                )

        # 3. handle columns with lists of strings (e.g. 'answer_variations')
        elif isinstance(first_element, list):
            df[col_name] = df[col].apply(
                lambda lst: model.encode(lst).tolist() if isinstance(lst, list) and len(lst) > 0 else []
            )
    return df

# validate that the embeddings are generated correctly using a helper
def audit_all_embeddings(df: pd.DataFrame, 
                         text_columns: list, 
                         id_col: str = 'temp_qid') -> pd.DataFrame:
    """
    Audits a mix of scalar (string) and vector (list) columns for embedding integrity.
    Automatically infers the data shape and applies the correct vectorized checks.
    - AI generated.
    """
    errors = []

    for col in text_columns:
        emb_col = f"{col}_embeddings"

        # 1. Pipeline Guard: Did the embedding column even get created?
        if emb_col not in df.columns:
            errors.append(f"[PIPELINE ERROR] Missing expected embedding column: '{emb_col}'")
            continue

        # 2. Type Inference: Look at the first non-null row to figure out the shape
        first_valid_idx = df[col].first_valid_index()
        if first_valid_idx is None:
            continue  # Column is entirely empty, safely skip

        is_list = isinstance(df.loc[first_valid_idx, col], list)

        # 3. Apply the correct Vectorized Check
        if is_list:
            text_lengths = df[col].apply(lambda x: len(x) if isinstance(x, list) else 0)
            emb_lengths = df[emb_col].apply(lambda x: len(x) if isinstance(x, list) else 0)
            mismatch_mask = text_lengths != emb_lengths
        else:
            text_exists = df[col].apply(lambda x: isinstance(x, str) and len(x.strip()) > 0)
            emb_exists = df[emb_col].apply(lambda x: isinstance(x, list) and len(x) > 0)
            mismatch_mask = text_exists & (~emb_exists)

        # 4. Log specific errors for any broken rows
        broken_rows = df[mismatch_mask]
        for _, row in broken_rows.iterrows():
            row_id = row.get(id_col, "UNKNOWN_ID")
            if is_list:
                t_len = len(row.get(col, [])) if isinstance(row.get(col), list) else 0
                e_len = len(row.get(emb_col, [])) if isinstance(row.get(emb_col), list) else 0
                errors.append(
                    f"[{row_id}] List Mismatch in '{col}': {t_len} strings vs {e_len} vectors.")
            else:
                errors.append(
                    f"[{row_id}] Missing Vector in '{col}': Text exists but embedding dropped.")

    # 5. The Gatekeeper: halt if anything fails
    if errors:
        error_report = "\n".join(errors)
        raise ValueError(f"Pipeline Halted: Embedding Audit Failed!\n{error_report}")

    print(
        f"✅ Universal Audit Passed: Dimensional integrity verified across {len(text_columns)} columns.")
    return df

# helper to create batches of the synthetic df grouped by grounding text for dedup
# now we can compare the similarity scores for the sample:
def create_dedup_syn_batches(dedup_embedding_cols: List[str],
                             dataframe: pd.DataFrame,
                             generation_batches_dict: dict,
                             id_col_name: str = 'temp_qid',
                             source_ref_col_name: str = 'source_reference',
                             ) -> dict:
    """
    Groups synthetic data into processing batches based on source reference and 
    computes fast PyTorch cosine similarity matrices.

    This helper isolates the computationally heavy tensor math from downstream 
    Pandas and NetworkX operations by immediately converting the resulting 
    similarity matrices back into NumPy arrays.

    Args:
        dedup_embedding_cols (List[str]): List of column names containing the dense 
            vector embeddings (e.g., ['question_embeddings', ...]).
        dataframe (pd.DataFrame): The main dataset containing embeddings and metadata. 
            Passed by reference; not copied in memory to conserve RAM.
        generation_batches_dict (dict): A mapping of batch names to their associated 
            source references (e.g., {'batch_1': ['chapter_1', 'chapter_2']}).
        id_col_name (str, optional): The column name for the unique identifier. 
            Defaults to 'temp_qid'.
        source_ref_col_name (str, optional): The column name used to group the data 
            into discrete batches. Defaults to 'source_reference'.
            
    Returns:
        dict: A nested dictionary mapping batch names to their computed similarity 
            matrices for columns in `dedup_embedding_cols` and parallel lists of question IDs.
            Format per batch:
            {
                'batch_qids': List[str],
                '<col_name>_sim_matrix': np.ndarray, 
                ...
            }
    """
    # 1. seutp
    batch_sim_matrix_dict = {}

    # 2. loop through generation dict
    for batch_name, chapters in generation_batches_dict.items():
        # 2.1. create subset of questions for each generation batch
        subset = dataframe.loc[dataframe[source_ref_col_name].isin(chapters)]
        # prevent creating empty tensor placeholders for batches with no matching data
        if not subset.empty:
            batch_sim_matrix_dict[batch_name] = {}
            # lock in the parallel array of question ids to map back from tensor coordinates
            batch_sim_matrix_dict[batch_name]['batch_qids'] = subset[id_col_name].tolist()
            for col in dedup_embedding_cols:
                # sbert embeddings are dense vectors can use tensors for fast simillilarity calc
                tensor = torch.tensor(subset[col].tolist())
                # convert to numpy after calc to work with graphs (networkx, pandas)
                batch_sim_matrix_dict[batch_name][f"{col}_sim_matrix"] = util.cos_sim(
                    tensor, tensor).numpy()
        else:
            print(f"Skipping {batch_name}: no matching chapters found in current data.")

    return batch_sim_matrix_dict              

## step 2.1: cross-type deduplication

# helper for group_duplicates method (creates duplicate clusters using source_quote
# similarity matrix and graph analysis)
def _generate_graph_clusters(qids: list, 
                             sq_score_df: pd.DataFrame
                             ) -> Tuple[List[List[str]], nx.Graph]:
    """
    Groups questions into duplicate clusters based on pairwise similarities.

    Args:
        qids (list): All question IDs to be represented in the graph.
        edges_df (pd.DataFrame): Dataframe of pairs exceeding similarity thresholds.
            Must include 'qids_rows', 'qids_cols', and similarity score columns.

    Returns:
        duplicate_groups (list): Lists of IDs grouped by connected components.
        G (nx.Graph): The underlying graph object with score attributes.  
    """
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

# helper for group_duplicates method (takes the clusters from the graph analysis &
# creates an audit df of similiarty of questions to its golden record in one table)
def _create_dedup_audit_df(duplicate_groups: List[List[str]],
                           original_df: pd.DataFrame,
                           threshold_sq: float,
                           id_col_name: str,
                           qids: List[str], 
                           sq_mat: np.ndarray,
                           ques_mat: np.ndarray,
                           ans_mat: np.ndarray) -> pd.DataFrame:
    """
    Creates an audit table for duplicate clusters, pulling precise similarity 
    scores from the original matrices relative to each cluster's golden record.

    Args:
        duplicate_groups (List[List[str]]): Lists of question IDs grouped by 
            connected components (clusters).
        original_df (pd.DataFrame): The original batch dataframe containing 
            question text and metadata (must include 'temp_qid' for synthetic or 
            'original_question_id' for legacy, 'question_type', 'source_quote',
            'question', 'answer', 'source_reference').
        threshold_sq (float): The similarity threshold used to generate the 
            initial source quote edges.
        qids (List[str]): List of parallel question IDs corresponding to the 
            rows and columns of the similarity matrices.
        sq_mat (np.ndarray): The 2D numpy array of source quote similarity scores.
        ques_mat (np.ndarray): The 2D numpy array of question similarity scores.
        ans_mat (np.ndarray): The 2D numpy array of answer similarity scores.

    Returns:
        pd.DataFrame: A formatted audit dataframe sorted by cluster and hierarchy, 
            containing the relative similarity scores and a boolean 'is_duplicate' flag.
    """
    # 1. filter the batch_df to get only the questions that are in the duplicate groups
    all_dup_ids = set(qid for group in duplicate_groups for qid in group)
    subset_df = original_df.loc[original_df[id_col_name].isin(all_dup_ids)].copy()

    # 2. assign group ids to each question df
    # 2.1. create a dict that maps a group_id to each cluster
    id_to_cluster_map = {}
    for i, group in enumerate(duplicate_groups):
        group_id = f"Group_{i:04d}"
        for qid in group:
            id_to_cluster_map[qid] = group_id
    # 2.2. map the group id by qid into df:
    subset_df['audit_cluster_id'] = subset_df[id_col_name].map(id_to_cluster_map)

    # 3. Assign duplicate flag
    # 3.1.  assign hierarchy to eqch question based on question type
    subset_df['qtype_hierarchy']= subset_df['question_type'].map(qtype_hierarchy_map)
    # 3.2. within each group, keep the question with the lowest hiearchy num
    subset_df = subset_df.sort_values(by=['audit_cluster_id', 'qtype_hierarchy'], ascending=True)
    subset_df['is_duplicate_sq_only'] = subset_df.duplicated(subset='audit_cluster_id', keep='first')

    #4. add the source_quoote threshold column
    subset_df['source_quote_threshold'] = threshold_sq

    # 5. add the fine-pass similarity scores (question, answer) from the original np sim matrices
    # to get scores relative to the golden record within the group

    # 5.1. within each group, attach its golden record temp_qid to each question for reference
    # create a map of golden qid for every cluster id.
    golden_record = subset_df.loc[~subset_df['is_duplicate_sq_only']
                                  ].set_index('audit_cluster_id')[id_col_name]
    # create a new column that provides the golden record for each question based on the dup 
    # cluster it belongs to
    subset_df['golden_qid'] = subset_df['audit_cluster_id'].map(golden_record)

    # 5.2. lookup index for np arrays (sim matrices) since qid & sim matrices are parallel arrays
    qid_indexer = pd.Series(range(len(qids)), index=qids)  # maps position to the qid label

    # 5.3. create look up coords for matrices row col - golden record x question
    g_idx = subset_df['golden_qid'].map(qid_indexer)
    t_idx = subset_df[id_col_name].map(qid_indexer)
    # explicitly turn indices to integer NumPy arrays 
    # (resolves Pylance warnings and prevents float-indexing crashes)
    g_idx_np = g_idx.to_numpy(dtype=int)
    t_idx_np = t_idx.to_numpy(dtype=int)
    
    # 5.4 calculate the composite similarity scores  
    composite_sim = (
        (sq_mat * SIM_WEIGHTS['quote']) +
        (ques_mat * SIM_WEIGHTS['question'])+
        (ans_mat * SIM_WEIGHTS['answer']) 
    )
    # 5.5 Extract the parallel scores using NumPy advanced indexing (using .values for safety)
    subset_df['rel_sq_sim'] = np.round(sq_mat[g_idx_np, t_idx_np],4)
    subset_df['rel_q_sim']  = np.round(ques_mat[g_idx_np, t_idx_np],4)
    subset_df['rel_a_sim']  = np.round(ans_mat[g_idx_np, t_idx_np],4)
    subset_df['composite_sim'] = np.round(composite_sim[g_idx_np, t_idx_np],4)

    # 7. Create view audit_df"
    column_order = [id_col_name, 'audit_cluster_id', 'question_type',
                    'is_duplicate_sq_only', 'golden_qid', 'qtype_hierarchy',
                    'source_quote_threshold', 'composite_sim',
                    'rel_sq_sim', 'rel_a_sim','rel_q_sim', 'source_quote',
                    'question', 'answer', 'source_reference']

    return subset_df[column_order]

# MAIN CROSS-TYPE DEDUPLICATION METHOD FOR SYNTHETIC GENEREATED Qs
def group_duplicates(batch_df: pd.DataFrame,
                     id_col_name:'str', 
                     batch_sim_matrix_dict: dict,
                     threshold_sq: float, 
                     use_secondary_pass: bool = True,
                     threshold_composite: float = 0.85,
                     min_ans_sim: float = 0.80):
    """
    Executes a two-pass semantic deduplication engine across batched text embeddings.

    This function identifies duplicate question pairs by first clustering them via 
    a high-level graph pass (source quote similarity only), and then verifies in a second
    pass using a fine composite score (combining question, answer, and quote similarities). 
    It is designed to safely handle highly contextual data where questions may share 
    identical source text but require distinct answers.
    
    Args:
        batch_df (pd.DataFrame): The original synthetically generated Q&A dataset containing
        the text features and metadata for the current run.
        id_col_name (str): The column name representing the unique identifier for 
            each row (e.g., 'temp_qid').
        batch_sim_matrix (dict): A nested dictionary of pre-computed cosine similarity 
            matrices (converted to NumPy arrays, not Tensors) mapped by generation batch ID.
            The generation batches are questions grouped by the source_reference pairing in 
            their generating prompt (inc in metadata of run)
            Expected structure per batch:
            {
                'batch_qids': list[str],
                'source_quote_embeddings_sim_matrix': np.ndarray,
                'question_embeddings_sim_matrix': np.ndarray,
                'answer_embeddings_sim_matrix': np.ndarray
            }
        threshold_sq (float, optional): The minimum cosine similarity required between 
            source quotes to establish an edge during the first-pass graph clustering. 
            Defaults to 0.85.
        use_secondary_pass (bool, optional): If True, applies multi-factor validation 
            against a cluster's 'Golden Record'. Defaults to True as the primary 
            safety mechanism against false positives.
        threshold_composite (float, optional): The minimum weighted composite similarity 
            required to confirm a duplicate during the fine pass. Defaults to 0.70.
        min_ans_sim (float, optional): A hard safety gate; the minimum answer similarity 
            required to prevent deleting distinct questions drawn from the same quote. 
            Defaults to 0.80.

    Returns:
        pd.DataFrame: A comprehensive master audit log of all identified duplicate 
            clusters. Contains the original text, calculated similarity scores, 
            Golden Record assignments, and the tiered boolean flags 
            (`is_duplicate_sq_only` and `is_duplicate_composite`). Returns an 
            empty DataFrame if no duplicates are detected across any batches.    
    """
    original_df = batch_df.copy()
    batch_results = []

    for batch in batch_sim_matrix_dict:

        batch_data = batch_sim_matrix_dict[batch]
        # unpack dict for batch (convert tensor to np.array)
        qids, sq_mat, ques_mat, ans_mat = (
            batch_data['batch_qids'],
            batch_data['source_quote_embeddings_sim_matrix'],
            batch_data['question_embeddings_sim_matrix'],
            batch_data['answer_embeddings_sim_matrix']
        )

        # 1. COARSE PASS: create duplicate groups based on source_quote first
        # 1.1. creates a boolean matrix of all pairs that pass threshold
        rows, cols = np.where(np.triu(sq_mat > threshold_sq, k=1))

        # 1.2. keep actual similarity score values as a signal along with coords.
        qids_array = np.array(qids)  # to allow fancy lookup
        sq_score_df = pd.DataFrame({
            'qids_rows'  : qids_array[rows].tolist(), 
            'qids_cols'  : qids_array[cols].tolist(),
            'sq_score'   : sq_mat[rows, cols],
            'ques_score' : ques_mat[rows, cols],
            'ans_score'  : ans_mat[rows, cols]
        })

        # 1.3 create graph cluster from the pairwise comparison
        duplicate_groups, G = _generate_graph_clusters(qids, sq_score_df)

        # 1.4. covert the duplicate groups into a df for easy viewing / auditing
        batch_audit_df = _create_dedup_audit_df(duplicate_groups, original_df, threshold_sq,
                                                id_col_name, qids, sq_mat, ques_mat, ans_mat)

        # 1.5. Add batch_name to df
        batch_audit_df.insert(0, 'batch_id', batch)

        # 2. FINE-PASS: create `is_duplicate_composite` based on question, answer similarity within dup groups
        if use_secondary_pass:
            # 2.1 duplicate conditions 
            ## can switch composite with individual threshold for question and answer if needed
            high_composite_score = (batch_audit_df['composite_sim'] > threshold_composite)
            not_golden_record = (batch_audit_df[id_col_name] != batch_audit_df['golden_qid'])
            answer_safety_gate = (batch_audit_df['rel_a_sim'] > min_ans_sim)

            # 2.2 create composite score flag and insert after is_duplicate_sq_only for clear comparison
            # get index of source_quote duplicate flag first
            sq_idx = list(batch_audit_df.columns).index('is_duplicate_sq_only')
            # create and insert new bool column
            batch_audit_df.insert(
                loc=sq_idx + 1,
                column='is_duplicate_composite', 
                value=(high_composite_score & not_golden_record & answer_safety_gate)
            )

        batch_results.append(batch_audit_df)

    # 4. Concat all batch dfs and return a master audit df
    if not batch_results:
        # If no duplicates were found in any batch, return an empty DataFrame
        print("No duplicates detected in any batch.")
        return pd.DataFrame()

    master_audit_df = pd.concat(batch_results, ignore_index=True)
    return master_audit_df

# Main deduplication ORCHESTRATOR (across question types, same source material, within same synthetic batch)
def deduplicate_synthetic_batch(synthetic_df: pd.DataFrame,
                                sbert_model_instance: SentenceTransformer,
                                generation_batches_dict: dict,
                                syn_id_col_name: str = 'temp_qid',
                                cols_to_embed: list = COLS_FOR_EMBEDDINGS,
                                embedding_col_names: list = EMBEDDING_COL_NAMES,
                                source_ref_col_name: str = 'source_reference',
                                threshold_source_quote: float = 0.80,
                                threshold_composite: float = 0.70,
                                min_ans_sim: float = 0.80,
                                second_pass_flag: bool = True,
                                ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Orchestrates the offline semantic deduplication pipeline for synthetic data batches.
    
    This function generates SBERT embeddings for structural columns, validates their 
    integrity, and runs a two-pass semantic verification (Source Quote overlap followed 
    by Composite Question/Answer overlap) to flag logically identical questions 
    generated from the same source material.
    
    Args:
        synthetic_df (pd.DataFrame): The raw generation batch dataframe.
        sbert_model_instance (SentenceTransformer): The singleton SBERT model for invariant vector generation.
        generation_batches_dict (dict): Configuration mapping for batch-level processing.
        syn_id_col_name (str): The column name representing the unique synthetic question ID.
        cols_to_embed (list): List of text columns that require SBERT embeddings.
        embedding_col_names (list): List of expected output column names for the generated embeddings.
        source_ref_col_name (str): The column name containing the source material reference.
        threshold_source_quote (float): Cosine similarity threshold for the first-pass source quote check.
        threshold_composite (float): Cosine similarity threshold for the second-pass Q&A composite check.
        min_ans_sim (float): Minimum answer similarity required to flag a duplicate (safety guardrail).
        second_pass_flag (bool): Whether to run the composite semantic check after the source quote check.
        
    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: A tuple containing:
            - audit_df: The summary dataframe containing duplicate flags and grouping IDs.
            - validated_embedding_df: The complete dataframe containing all generated and validated 
              SBERT vectors, ready for downstream processing without needing to recompute.
    
    """
    df = synthetic_df.copy()
    
    # 1. Create a new column with only MCQ distractors (without the answer) to generate separate embeddings for them
    distractors_df = append_text_distractors(df)
    
    # 2. Add embeddings to df
    #    create embeddings for all columns that need embeddings downstream in one go (not just for deduplication)
    embedding_df = generate_embeddings(dataframe = distractors_df,
                                       columns = cols_to_embed, 
                                       model = sbert_model_instance
                                      )
    #   validated embeddings created correctly (will throw error and halt pipeline if any issues with embedding creation)
    validated_embedding_df = audit_all_embeddings(df = embedding_df,
                                                  text_columns = cols_to_embed,
                                                  id_col = syn_id_col_name
                                                  )
    
    # 3. create deduplication batches for the synthetic tracer using existing generation_batches dict
    #    and generate similarity matrics for the embedding cols. Pass in the new df with embeddings (dedup_embedding_df)    
    batch_sim_matrix_full = create_dedup_syn_batches(dedup_embedding_cols= embedding_col_names,
                                                         dataframe = validated_embedding_df,  
                                                         generation_batches_dict = generation_batches_dict,
                                                         id_col_name= syn_id_col_name,
                                                         source_ref_col_name=source_ref_col_name
                                                         )
    # 4. Flag duplicates in the df and review audit df
    #    Run full two-pass semantic verification (Source Quote + Composite)
    audit_df= group_duplicates(batch_df = validated_embedding_df,
                               id_col_name= syn_id_col_name,
                               batch_sim_matrix_dict= batch_sim_matrix_full,
                               threshold_sq= threshold_source_quote,
                               use_secondary_pass=second_pass_flag,
                               threshold_composite=threshold_composite,
                               min_ans_sim=min_ans_sim)
    
    return audit_df, validated_embedding_df    

### --- STAGE 3: ALIGNMENT ---

# validate answer variations using embeddings similarity to the main answer (can be used for both legacy and synthetic data)
def flag_invalid_ans_variations(df: pd.DataFrame, 
                                rules: dict, 
                                question_type_col_name: str = 'question_type') -> pd.DataFrame:
    """_summary_

    :param df: _description_
    :param rules: _description_
    :param question_type_col_name: _description_, defaults to 'question_type'
    :return: _description_
    """
    result_df = df.copy()
    
    def validate_row(row):
        q_type = row.get(question_type_col_name, 'MCQ')
        ans_text = str(row['answer']).lower()           # Need raw text for substring check
        var_text_list = row['answer_variations']        # Need raw text for substring check
        ans_emb = row['answer_embeddings']
        var_embs = row['answer_variations_embeddings']
        
        if not isinstance(var_embs, list) or len(var_embs) == 0:
            return True 
            
        ans_tensor = torch.tensor(ans_emb)
        var_tensor = torch.tensor(var_embs)
        scores = util.cos_sim(ans_tensor, var_tensor)[0].tolist()
        
        thresholds = rules.get(q_type, [0.85])
        
        # Evaluate each variation against its specific threshold
        for i, (var_text, score) in enumerate(zip(var_text_list, scores)):
            var_text_clean = str(var_text).lower()
            
            # --- THE HEURISTIC BRIDGE (Substring Free Pass) ---
            # If the variation is inside the answer, or answer inside variation, it's a guaranteed match.
            if var_text_clean in ans_text or ans_text in var_text_clean:
                continue # Skips the math check and passes this variation!
                
            # --- THE MATH CHECK ---
            current_threshold = thresholds[i] if i < len(thresholds) else thresholds[-1]
            if score < current_threshold:
                return False # Fails the whole row if even one variation fails the math
                
        return True

    result_df['ans_variations_valid'] = result_df.apply(validate_row, axis=1)
    return result_df

# determine if the mcq options contain answer and distractors are sufficently different from answer.
def validate_mcq_options(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
    """
    Confirms the distractors are sufficiently distinct (based on delta) from the answer.
    This method is specialized for 'question_type' == 'MCQ'.
    AI -generated (Google Gemini 3 Pro)
    Args:
        df (pd.DataFrame): The dataset containing 'question_type', 'answer', 
            'mcq_options', 'answer_embeddings', and 'distractor_embs'.
        rules (dict): Dictionary containing 'answer_presence_min' and 
            'distractor_similarity_min' thresholds.

    Returns:
        pd.DataFrame: Dataframe with 4 new audit columns for MCQ quality control.
    """
    # 1. fail fast: make sure margins are provided in rules. if missing, cannot proceed.
    try:
        presence_min = rules['min_answer_presence']
        margin_min = rules['min_distractor_delta']
    except KeyError as e:
        raise KeyError(f"Pipeline Config Error: Missing required MCQ threshold {e}") from e

    result_df = df.copy()

    def check_row(row):
        # Safely handle both raw strings and Enum objects
        if str(row.get('question_type', '')) != 'MCQ':
            return True, True, None, None

        raw_answer = row.get('answer', '')
        raw_options = row.get('mcq_options', [])

        # Use utility + lower() for comparison
        clean_ans = clean_text_fn(raw_answer).lower()
        clean_opts = [clean_text_fn(opt).lower() for opt in raw_options]

        # 2. Perform the Verbatim Check
        # This catches if the LLM forgot to include the answer or misspelled it
        verbatim_presence = clean_ans in clean_opts

        # 3. Handle Duplicates 
        # If the answer appears twice, flag exactly why it failed.
        if clean_opts.count(clean_ans) > 1:
            return True, False, 0.0, "DUPLICATE_ANSWER_IN_OPTIONS"

        ans_emb = row.get('answer_embeddings')
        dist_embs = row.get('mcq_distractors_embeddings') 
        dist_texts = row.get('mcq_distractors')

        if ans_emb is None or dist_embs is None or dist_texts is None:
            return False, False, 0.0, "MISSING_PIPELINE_DATA"

        # alignment guard - checks if the text list and embedding list stay in sync
        if len(dist_texts) != len(dist_embs):
            return False, False, 0.0, f"MISMATCH: {len(dist_texts)} text vs {len(dist_embs)} embs"

        # synthetic reconstruction
        syn_mcq_options_embs = [ans_emb] + dist_embs
        syn_mcq_options_text = [row.get('answer')] + dist_texts

        ans_tensor = torch.tensor(ans_emb)
        opts_tensor = torch.tensor(syn_mcq_options_embs)
    
        # Calculate scores and pair with text
        scores = util.cos_sim(ans_tensor, opts_tensor)[0].tolist()
        scored_options = sorted(zip(scores, syn_mcq_options_text), reverse=True)

        # Extract the metrics
        top_score, _ = scored_options[0]
        runner_up_score, runner_up_text = scored_options[1]

        # Apply the logic
        # It must be there verbatim AND SBERT must see it as the top match
        presence_valid = verbatim_presence and (top_score >= presence_min)
        margin = top_score - runner_up_score
        distractors_valid = margin >= margin_min

        return presence_valid, distractors_valid, round(margin, 4), runner_up_text

    # Unpack into the 4 audit columns
    results = result_df.apply(check_row, axis=1)
    result_df['mcq_presence_valid'], result_df['mcq_distractors_valid'], \
    result_df['mcq_margin_score'], result_df['mcq_closest_distractor'] = zip(*results)

    return result_df

def validate_qtype_category_alignment(row) -> pd.Series:
    """
    Validates that the answer content aligns with both its Question Type 
    and its LLM-assigned Category.
    Returns: pd.Series with (is_valid, reason)
    """
    q_type = str(row.get('question_type', '')).upper()
    category = str(row.get('llm_predicted_category', '')).lower()
    answer = str(row.get('answer', '')).strip()
    
    if not answer:
        return pd.Series([False, "EMPTY_ANSWER"])

    word_count = len(answer.split())

    # 1. EX Checks: Must be substantive
    if q_type == 'EX':
        if word_count < 3:
            return pd.Series([False, f"EX_TOO_SHORT: {word_count} words"])
        return pd.Series([True, "PASS"])

    # 2. FR / MCQ Checks: Must be concise
    if q_type in ['FR', 'MCQ']:
        if word_count > 15:
            return pd.Series([False, f"{q_type}_TOO_LONG: {word_count} words"])
            
        #3. The Numerical/Date "Gold Standard" Checks
        # Handles "Number/Year" and future "Date" labels
        if any(k in category for k in ['number', 'year', 'date']):
            
            # Sub-Check A: Strict Year (Look for 4 digits)
            if 'date' in category:
                date_pattern = r'\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b'
                if not re.search(date_pattern, answer):
                    return pd.Series([False, "DATE_FORMAT_ERROR"])
            
            # Sub-Check B: Strict Year (ONLY if it's NOT also a 'number')
            # This prevents "Number/Year" from causing a False Negative for "7"
            elif 'year' in category and 'number' not in category:
                if not re.search(r'\b\d{4}\b', answer):
                    return pd.Series([False, "YEAR_FORMAT_ERROR"])
            
            # Sub-Check C: General Numerical (The "Safe" catch-all)
            # This handles "Number", "Number/Year", and any other digit-based logic
            else:
                if not any(char.isdigit() for char in answer):
                    return pd.Series([False, "NUMERICAL_MISMATCH"])

    return pd.Series([True, "PASS"])

## Synthetic deduplication against legacy / Gold dataset

def deduplicate_synthetic_against_legacy(synthetic_batch_df: pd.DataFrame,
                                         gold_legacy_df: pd.DataFrame,
                                         threshold_dict: dict):
    """
    Compares synthetic embeddings against legacy / Gold dataset embeddings.
    Flags for review or auto-deletes based on similarity thresholds.
    """
    # initialize
    syn_df = synthetic_batch_df.copy()

    q_threshold = threshold_dict['question']
    a_threshold = threshold_dict['answer']
    review_threshold = threshold_dict['hitl_review']

    actions = []
    closest_legacy_ids = []
    max_q_scores = []

    # 1. convert embedding columns to tensors
    syn_q_tensor = torch.tensor(np.array(syn_df['question_embeddings'].tolist()), dtype=torch.float32)
    syn_a_tensor = torch.tensor(np.array(syn_df['answer_embeddings'].tolist()), dtype=torch.float32)

    ref_q_tensor = torch.tensor(gold_legacy_df['question_embeddings'].tolist(), dtype=torch.float32)
    ref_a_tensor = torch.tensor(gold_legacy_df['answer_embeddings'].tolist(), dtype=torch.float32)

    # 2. calculate similarity 
    q_sims = util.cos_sim(syn_q_tensor, ref_q_tensor)
    a_sims = util.cos_sim(syn_a_tensor, ref_a_tensor)

    # 3. compare each synthetic question to against the closest Gold / legacy match
    for i in range(len(syn_df)):

        # 3.1. id best gold / legacy match for each synthetic q (max score)
        best_match_idx = int(torch.argmax(q_sims[i]).item())
        # create an array of best scores for questions and the gold / legacy 'original_question_id``
        best_q_sim = q_sims[i][best_match_idx].item()
        best_a_sim = a_sims[i][best_match_idx].item()
        legacy_id = gold_legacy_df.iloc[best_match_idx].get('original_question_id', best_match_idx)

        # 3.2. determine tags based on predefined thresholds:
        if best_q_sim >= q_threshold and best_a_sim >= a_threshold:
            action = "AUTO_DELETE"
        elif best_q_sim >= review_threshold:
            # High question similarity, but maybe a different answer or slightly below auto-delete
            action = "REVIEW"
        else:
            action = "KEEP"
        actions.append(action)
        closest_legacy_ids.append(legacy_id)
        max_q_scores.append(round(best_q_sim, 4))

    # 4. Attach results to the dataframe
    syn_df['dedupe_action'] = actions
    syn_df['closest_legacy_id'] = closest_legacy_ids
    syn_df['max_similarity_score'] = max_q_scores

    # 5. print a summary
    print("Deduplication Summary:")
    print(syn_df['dedupe_action'].value_counts())

    return syn_df    

## Serialization for Parquet saves

def pydantic_to_pyarrow_schema(model) -> pa.Schema:
    """
    Builds a PyArrow schema from a Pydantic V2 model.
    Strips Optional/Union wrappers, maps Python types to PyArrow types.
    Tracer-level: handles the known SilverMCQ column types only.
    AI-generated (Claude Sonnet 4.6)
    """

    PY_TO_PA = {
        str:   pa.string(),
        int:   pa.int64(),
        float: pa.float64(),
        bool:  pa.bool_(),
    }

    def unwrap_optional(annotation):
        origin = get_origin(annotation)
        is_union = (origin is Union) or (
            hasattr(types, "UnionType") and isinstance(annotation, types.UnionType)
        )
        if is_union:
            inner = [a for a in get_args(annotation) if a is not type(None)]
            return inner[0] if inner else annotation
        return annotation

    def resolve(annotation) -> pa.DataType:
        annotation = unwrap_optional(annotation)
        origin = get_origin(annotation)
        args   = get_args(annotation)

        if origin is Literal:
            return resolve(type(args[0]))
        if origin is list:
            inner = resolve(args[0]) if args else pa.string()
            return pa.list_(inner)
        if origin is dict:
            return pa.string()  # JSON-serialized per design doc

        return PY_TO_PA.get(annotation, pa.string())

    fields = [
        pa.field(name, resolve(field_info.annotation), nullable=True)  # always nullable
        for name, field_info in model.model_fields.items()
    ]

    return pa.schema(fields)

def serialize_complex_cols_to_json(df: pd.DataFrame, complex_cols: list[str]) -> pd.DataFrame:
    """
    Serializes columns containing complex Python objects (dicts/lists) into JSON strings. 
    This is required for PyArrow/Parquet compatibility in the Silver tier.
    """
    df_serialized = df.copy()
    for col in complex_cols:
        if col in df_serialized.columns:
            df_serialized[col] = df_serialized[col].apply(
                lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x
            )
            
    return df_serialized

def replace_nans_with_none(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts Pandas float NaNs to native Python Nones across an entire DataFrame.
    Crucial for PyArrow serialization of complex/array columns where Pandas' 
    default float-based NaNs cause schema mismatch errors.
    """
    df_clean = df.copy()
    for col in df_clean.columns:
        # Cast to object so Pandas allows us to insert None without forcing it back to NaN 
        df_clean[col] = df_clean[col].astype(object)
        # Use native boolean indexing to find all nulls and overwrite them with None
        df_clean.loc[df_clean[col].isna(), col] = None

    return df_clean

def validate_null_integrity(df: pd.DataFrame, 
                            partially_null_cols: list[str],
                            fully_null_cols: list[str]| None = None):
    """
    Asserts that no Pandas float NaNs leaked into the DataFrame, and verifies 
    that fully null columns (like legacy source_quotes) are 100% None.
    """
    total_rows = len(df)
    
    if fully_null_cols:
        for col in fully_null_cols:
            nan_count = df.apply(lambda x: isinstance(x, float) and math.isnan(x), axis=1).sum()
            none_count = df[col].apply(lambda x: x is None).sum()
            assert nan_count == 0, f"FAIL: Found {nan_count} lingering NaNs in '{col}'."
            assert none_count == total_rows, \
                f"FAIL: Expected {total_rows} Nones in '{col}', found {none_count}."

    if partially_null_cols:
        for col in partially_null_cols:
            nan_count = df[col].apply(lambda x: isinstance(x, float) and math.isnan(x)).sum()
            assert nan_count == 0, f"FAIL: Found {nan_count} lingering NaNs in '{col}'."
            
    print("✅ Null integrity assertions passed.")

def prepare_parquet_table(df: pd.DataFrame, 
                          pydantic_model,
                          partially_null_cols: list[str],
                          fully_null_cols: list[str]| None = None) -> pa.Table:
    """
    Ai generated.
    Prepares a DataFrame for Parquet storage by:
    1. Converting NaNs to None.
    2. Asserting null integrity for fully and partially empty columns.
    3. Applying a PyArrow schema derived from the Pydantic model.
    4. Asserting key column types on the resulting table.

    Args:
        df: Input DataFrame to prepare.
        pydantic_model: Pydantic model to derive the PyArrow schema from.
        fully_null_cols: Columns expected to be entirely None (e.g. source_quote for Legacy).
        partially_null_cols: Columns expected to have no lingering NaNs but may be partially filled 
                             (e.g. mcq_options).
    Returns:
        pa.Table: A strictly typed PyArrow table ready for Parquet storage.
    """
    # 1. Transform: convert NaNs to None
    df_clean = replace_nans_with_none(df)

    # 2. Validate: confirm that NaNs were replaced
    validate_null_integrity(df_clean, partially_null_cols, fully_null_cols)

    # 3. Build PyArrow schema from Pydantic model and convert
    schema = pydantic_to_pyarrow_schema(pydantic_model)
    table = pa.Table.from_pandas(df_clean, schema=schema, preserve_index=False)

    # 5. Assert key column types on the resulting table
    assert pa.types.is_string(table.schema.field('question').type), \
        "Type Mismatch: 'question' is not a String!"
    assert pa.types.is_list(table.schema.field('mcq_options').type), \
        "Type Mismatch: 'mcq_options' is not a List!"
    assert pa.types.is_string(table.schema.field('mcq_options').type.value_type), \
        "Type Mismatch: 'mcq_options' does not contain Strings!"
    assert pa.types.is_list(table.schema.field('question_embeddings').type), \
        "Type Mismatch: 'question_embeddings' is not a List!"
    assert pa.types.is_float64(table.schema.field('question_embeddings').type.value_type), \
        "Type Mismatch: 'question_embeddings' does not contain Floats!"

    return table

# add `master_id` to Silver dataset
def assign_master_ids(df: pd.DataFrame, length: int = 8) -> pd.DataFrame:
    """
    Assigns a deterministic, content-based master_id to each row.
    Derived from question_type + question + answer via MD5 base64url hash.
    Assigned at Silver promotion — immutable and carried forward to Gold.
    AI-Generated (Claude Sonnet 4.6 ext)
    Args:
        df: Silver-tier DataFrame.
        length: Number of base64url characters to use for the ID (default 8).
    Returns:
        DataFrame with master_id column prepended.
    """
    def _hash(row):
        payload = f"{row['question_type']}_{row['question']}_{row['answer']}"
        hash_bytes = hashlib.md5(payload.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(hash_bytes).decode('utf-8').rstrip('=')[:length]

    df = df.copy()
    df.insert(0, 'master_id', df.apply(_hash, axis=1))

    # guard: catch any collisions immediately
    assert df['master_id'].is_unique, "FAIL: master_id collision detected — review payload uniqueness."

    return df

# REQUIRED for silver reading - to ensure complex columns are rehydrate as they are read.
def load_silver_parquet(file_path: str, complex_cols: list[str] | None = None) -> pd.DataFrame:
    """
    Standardized reader for Silver tier Parquet files.
    Automatically handles vectorized JSON extraction for complex columns
    so downstream tasks don't need to track serialization schemas.
    """
    
    if complex_cols is None:
        complex_cols = SILVER_COMPLEX_COLS
    
    # 1. Fast native read
    df = pd.read_parquet(file_path)

    # 2. Automated Vectorized Rehydration
    for col in complex_cols:
        if col in df.columns:
            # Vectorized load: much faster than df.apply(lambda) row-by-row
            # Note: handles None/NaN safely
            df[col] = df[col].apply(lambda x: json.loads(x) if pd.notnull(x) else x)
      
    return df
