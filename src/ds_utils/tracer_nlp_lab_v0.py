"""
Project: SVE (ref implementation: Harry Potter Trivia)
PHASE 2 Tracer -> Context Refinery: NLP Lab (Answer checking logic)
"""
## setup / imports
from typing import List, Tuple
import pandas as pd
import numpy as np
from sentence_transformers import util
import torch
from rapidfuzz import fuzz
import regex as re
from core.embeddings import get_sbert_model, sbert_settings
from runtime import player

## constants and thresholds
# thresholds
FUZZY_THRESHOLD = 85            # 85% character similarity (catches 1-2 letter typos)
SEMANTIC_THRESHOLD = 0.9        # SBERT cosine similarity
DISTRACTOR_DELTA = 0.30         # player answer comparison against distractors vs. correct answer
AMBIGUOUS_ANS_THRESHOLD = 0.60  # for enity_ref matches - lower threshold for sim score at which to check  
ENTITY_REF_MATCH_BOOST = 0.10   # sim score boost if player used a know alias or synoym (inject domain understanding to vanilla sbert) 

# loaded model from singleton cache (sbert model defined centrally)
model = get_sbert_model()

## 1- dataset preprocessing

## 1.1: Add tensors for embedding columns

# helper to convert list of arrays into a single 2D tensor,
# handling edge cases for empty/missing data and read-only Parquet arrays
def to_matrix_tensor(x):
    """
    Handles read-only Parquet arrays and list-of-arrays,
    converting them into a single, writable 2D PyTorch Tensor.
    AI-generated (Google Gemini 3 pro)
    """
    if x is None or not hasattr(x, '__len__') or len(x) == 0:
        return None
    try:
        clean_2d_array = np.stack(x).astype(sbert_settings.numpy_dtype) # Standardized dtype
        return torch.from_numpy(clean_2d_array)
    except Exception as e:
        print(f"Warning: Failed to convert matrix. Error: {e}")
        return None

def prepare_runtime_tensors(dataframe: pd.DataFrame, 
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
        matrix_list = [to_matrix_tensor(x) for x in tensor_df[col]]
        # Wrap in pd.Series to satisfy Pylance __setitem__ overloads
        tensor_df[col_name] = pd.Series(matrix_list, index=tensor_df.index)

    return tensor_df

## 2- ANSWER LOGIC HELPERS

### --- TEXT ANSWERS ---

### common helpers

# FOR MCQ & FR Only: quick direct answer check.    
def check_exact_match(player_answer: str, correct_answer: str) -> dict | None:
    """ TIER 1: Exact match of player answer to Gold dataset correct answer for FR, MCQ"""
    if player_answer == correct_answer: 
        return {"is_correct": True, "resolution_tier": "exact", "fuzzy_score": 100}
    return None    

# FOR MCQ & FR Only: quick fuzzy answer check. 
def check_fuzzy_match(player_answer: str, correct_answer: str, fuzzy_threshold: int) -> dict:
    """TIER 2: Fuzzy match of player answer. Always returns the score for telemetry."""
    fuzzy_score = fuzz.ratio(player_answer, correct_answer)
    # if pass:
    if fuzzy_score >= fuzzy_threshold:
        return {"is_correct": True, "resolution_tier": "fuzzy", "fuzzy_score": fuzzy_score}
    # If fails, return status / score
    return {"is_correct": False, "fuzzy_score": fuzzy_score}

# central helper for all question types for encoding player answers for semantic checks
def encode_player_answer(player_answer: str) -> torch.Tensor:
    """
    Centralized SBERT encoder enforcing SVE system invariants.
    
    Architectural Defaults:
    - Memory Safety: Locks to Singleton model to prevent RAM duplication and OOM crashes.
    - Data Integrity: Locks to global dtype SOT to prevent Medallion precision drift.
    
    NOTE: This is intentionally designed as a closed system for the Tracer phase. 
    Dependency injection parameters (model, dtype) can be added later if isolated 
    unit testing requires them.
    
    Args:
        player_answer (str): Normalized text input.   
    Returns:
        torch.Tensor: 1D tensor calibrated for SVE vector math.
    """
    # Singleton SOT by default to enforce system invariant
    active_model = get_sbert_model()
    active_dtype =  sbert_settings.tensor_dtype
    
    tensor = active_model.encode(player_answer, convert_to_tensor=True)
    return tensor.to(active_dtype) # standardized dtype

# FOR MCQ, FR types only: check for horizontal variations (synonyms, aliases) w. matrix comparison of answer variations
def check_semantic_variations(player_answer_tensor: torch.Tensor,
                               correct_ans_tensor: torch.Tensor,
                               correct_answer_variation_tensor_matrix: torch.Tensor| None = None
                               ) -> Tuple[float, bool]:
    """
    TIER 3 HELPER: Calculates highest cosine similarity against Gold Answer and Variations.
    Safely handles cases where a question has no acceptable variations.
    
    Returns:
        Tuple[float, bool]: (best_similarity_score, matched_variation_flag)
    """
    
    # 1. check main Gold answer
    # util.cos_sim returns a matrix; .item() gets the float for 1x1 results
    main_ans_score = util.cos_sim(player_answer_tensor, correct_ans_tensor).item()  # main answer similarity
    
    # 2. Check similarity against answer_variations for partial or shorthand answers 
    max_var_score = 0.0
    # check only if variations exist
    if correct_answer_variation_tensor_matrix is not None and len(correct_answer_variation_tensor_matrix) > 0:
        ans_variation_scores = util.cos_sim(player_answer_tensor, correct_answer_variation_tensor_matrix)[0]
        max_var_score = torch.max(ans_variation_scores).item() # Extract float first 
    
    # 3. pick the highest score 
    correct_ans_score = max(main_ans_score, max_var_score)
    
    # 4. track whether player matched main answer or a variation for telemtry (ans quality).
    matched_variation = (max_var_score > main_ans_score)
    
    return (correct_ans_score, matched_variation)

### 2.1 MCQ (multiple chocice)

# MCQ with a 'text' answer type (can be evaluated with fuzzy matching and semantic similarity)

def check_mcq_answer(player_answer:str, 
                     gold_answer: str,
                     gold_ans_tensor: torch.Tensor,
                     answer_variation_tensor_matrix: torch.Tensor,
                     distractor_tensor_matrix: torch.Tensor,
                     fuzzy_threshold: int = FUZZY_THRESHOLD,
                     semantic_threshold: float = SEMANTIC_THRESHOLD,
                     distractor_delta: float = DISTRACTOR_DELTA) -> dict:
    """
    Evaluates a player's multiple-choice answer using a 3-Tier logic.
    
    This function utilizes a 'shift-left' architecture. It relies on precomputed 
    tensor matrices for variations and distractors to evaluate shorthand and 
    partial answers mathematically, without requiring complex string parsing.

    The 3 Tiers of Evaluation:
    --------------------------
    - Tier 1 (Exact): Instant pass for perfect string matches (O(1) fast path).
    - Tier 2 (Fuzzy): Levenshtein distance check to catch minor typos.
    - Tier 3 (Vector): SBERT cosine similarity check against the Gold Answer 
      and an array of acceptable Variations, gated by a Margin delta against Distractors.
      
    WARNING: Contractual Assumption
    This function expects `player_answer` to be pre-normalized 
    (lowercased, stripped of trailing whitespace). Do not pass raw user input directly 
    to this method. Use the `normalize_player_input()` upstream helper first.  

    Args:
        player_answer (str): The normalized text input submitted by the player.
        gold_answer (str): The primary, perfect factual answer.
        gold_ans_tensor (torch.Tensor): 1D float32 tensor of the gold_answer.
        answer_variation_tensor_matrix (torch.Tensor): 2D float32 matrix containing 
            embeddings of acceptable shorthands and partial answers.
        distractor_tensor_matrix (torch.Tensor): 2D float32 matrix containing 
            embeddings of the incorrect MCQ options.
        fuzzy_threshold (int, optional): Minimum RapidFuzz ratio to pass Tier 2. 
            Defaults to FUZZY_THRESHOLD.
        semantic_threshold (float, optional): Minimum cosine similarity required 
            in Tier 3. Defaults to SEMANTIC_THRESHOLD (e.g., 0.70).
        distractor_delta (float, optional): The minimum mathematical margin required 
            between the best correct match and the closest distractor match. 
            Defaults to DISTRACTOR_DELTA (e.g., 0.15).

    Returns:
        dict: A metrics payload containing the verification results:
            - 'is_correct' (bool): Final evaluation result.
            - 'tiers_required' (int): Which tier (1, 2, or 3) resolved the logic.
            - 'fuzzy_score' (int): The RapidFuzz ratio (0-100).
            - 'sim_correct_ans' (float): Best SBERT score against Gold or Variations.
            - 'sim_distractor' (float): Best SBERT score against any Distractor.
            - 'margin' (float): (sim_correct_ans - sim_distractor).
    """
    # confirm preprocessing in place
    assert player_answer == player_answer.lower(), "CRITICAL: player_answer must be lowercased before reaching the MCQ checker." 

    # normalization of player ans is handled upstream of question_type speciifc helper
    metrics = {
        "is_correct": False,  # default to incorrect until proven otherwise
        "resolution_tier": "unresolved", # track how many tiers of evaluation were needed to determine correctness
        "fuzzy_score": 0, # track fuzzy score for debugging,
        "telemetry":{
            "sim_correct_ans": 0.0, # track semantic similarity score with gold / correct answer
            "sim_distractor": 0.0, # track semantic similarity score with closest distractor
            "margin": 0.0, # diff between player-gold similarity and player-distractor similarity for semantic tier,
            "matched_variation": False # whether the player answer matched a variation (shorthand) rather than the main gold answer (telemetry placeholder)
        }
    }
    
    # TIER 1: fast path (exact match) --> use case: perfect answers
    t1_result = check_exact_match(player_answer, gold_answer)
    if t1_result:
        metrics.update(t1_result)
        return metrics
    
    # TIER 2: intermediate path (fuzzy match -> use case: typos, spelling mistakes in short ans (FR, MCQ)
    t2_result = check_fuzzy_match(player_answer, gold_answer, fuzzy_threshold)
    metrics["fuzzy_score"] = t2_result["fuzzy_score"] # Log the score regardless of pass/fail
    if t2_result["is_correct"]:
        metrics.update(t2_result)
        return metrics
    
    # TIER 3: semantic logic (resolution path)
    # 1. encode player answer using helper
    player_tensor = encode_player_answer(player_answer)
    
    # 2. calculate similarity scores (against main gold correct answer, answer variations and find most similar) with helper
    correct_ans_score, matched_variation = check_semantic_variations(player_tensor,
                                                                     gold_ans_tensor,
                                                                     answer_variation_tensor_matrix)
    
    # 2.2: difference to distractors
    # For the matrix [N, 384], cos_sim returns [1, N]. [0] gets the vector of scores.
    distractor_scores = util.cos_sim(player_tensor, distractor_tensor_matrix)[0]
    max_dist_score = torch.max(distractor_scores).item()
    
    margin = correct_ans_score - max_dist_score
    
    # 3. update metrics
    metrics['telemetry'].update({
        "sim_correct_ans": round(correct_ans_score, 4),
        "sim_distractor": round(max_dist_score, 4),
        "margin": round(margin, 4),
        "matched_variation": matched_variation, # True if a variation (likely shorthand used)
    })
    
    if correct_ans_score >= semantic_threshold and margin >= distractor_delta:
        metrics.update({"is_correct": True, "resolution_tier": "semantic"})
    else:
        metrics.update({"is_correct": False, "resolution_tier": "failed_semantic"}) 
    
    return metrics

### 2.2 FR (Factual Recall)

def check_fr_answer(player_answer: str, 
                    gold_answer: str,
                    entity_refs: List[str],
                    gold_ans_tensor: torch.Tensor,
                    answer_variation_tensor_matrix: torch.Tensor, 
                    fuzzy_threshold: int = FUZZY_THRESHOLD,
                    semantic_threshold: float = SEMANTIC_THRESHOLD,
                    ambiguous_ans_threshold: float = AMBIGUOUS_ANS_THRESHOLD,
                    entity_boost_modifier: float = ENTITY_REF_MATCH_BOOST):
    """
    Evaluates a player's Factual Recall (open-text) answer using a 3-Tier logic.
    
    Because FR lacks the safety net of MCQ distractors, this function utilizes a stricter 
    baseline semantic threshold combined with a *entity boost*. It mathematically 
    rescues ambiguous SBERT scores by dynamically injecting domain knowledge (proper nouns) 
    before failing the player.

    The 3 Tiers of Evaluation:
    --------------------------
    - Tier 1 (Exact): Instant pass for perfect string matches (O(1) fast path).
    - Tier 2 (Fuzzy): Levenshtein distance check to catch minor typos.
    - Tier 3 (Semantic & Entity Boost): SBERT cosine similarity check against the Gold Answer 
      and acceptable variations. If the score falls into the ambiguous range, the engine 
      uses word-boundary Regex to check for core domain entities, applying a score boost
      if found.
      
    WARNING: Contractual Assumption
    This function expects `player_answer` and all strings within `entity_refs` to be 
    pre-normalized (lowercased, stripped of trailing whitespace). Do not pass raw user 
    input directly to this method. Use the `normalize_player_input()` upstream helper first.  

    Args:
        player_answer (str): The normalized text input submitted by the player.
        gold_answer (str): The primary, perfect factual answer.
        entity_refs (List[str]): A list of pre-normalized core domain entities (proper nouns) 
            used to trigger the Tier 3.5 score boost.
        gold_ans_tensor (torch.Tensor): 1D float32 tensor of the gold_answer.
        answer_variation_tensor_matrix (torch.Tensor): 2D float32 matrix containing 
            embeddings of acceptable shorthands and partial answers.
        fuzzy_threshold (int, optional): Minimum RapidFuzz ratio to pass Tier 2.
            Defaults to FUZZY_THRESHOLD.
        semantic_threshold (float, optional): Minimum cosine similarity required 
            in Tier 3 for a clean pass. Defaults to SEMANTIC_THRESHOLD (e.g., 0.80).
        ambiguous_ans_threshold (float, optional): The lower-bound similarity score 
            required to qualify for the Regex Entity Boost check. Defaults to 
            AMBIGUOUS_ANS_THRESHOLD (e.g. 0.70).
        entity_boost_modifier (float, optional): The mathematical boost applied to the 
            base similarity score if an entity match is found. Defaults to 
            ENTITY_REF_MATCH_BOOST (e.g. 0.10).

    Returns:
        dict: A metrics payload containing the verification results:
            - 'is_correct' (bool): Final evaluation result.
            - 'resolution_tier' (str): Which specific path resolved the logic 
              (e.g., 'semantic_pass', 'semantic_boosted', 'failed_semantic_threshold').
            - 'fuzzy_score' (int): The RapidFuzz ratio (0-100).
            - 'telemetry' (dict): Granular data for analytics and MLOps:
                - 'base_sim_score' (float): Best raw SBERT score before any boosts.
                - 'matched_variation' (bool): True if the variation matrix yielded the highest score.
                - 'boost_applied' (float): The exact mathematical boost added.
                - 'matched_entity_ref' (str | None): The specific entity string that triggered the boost.
                - 'final_boosted_score' (float): The final score evaluated against the threshold.
    """
    # confirm preprocessing in place
    assert player_answer == player_answer.lower(), "CRITICAL: player_answer must be lowercased before reaching the FR checker." 
    
    # initialze FR metrics dict
    metrics = {
        "is_correct": False,  # default to incorrect until proven otherwise
        "resolution_tier": "unresolved", # track how many tiers of evaluation were needed to determine correctness
        "fuzzy_score": 0, # track fuzzy score for debugging,
        "telemetry":{
            "base_sim_score": 0.0,
            "matched_variation": False,
            "boost_applied": 0.0, 
            "final_boosted_score": 0.0
            }
    }
    
    # TIER 1: fast path (exact match) --> use case: perfect answers
    t1_result = check_exact_match(player_answer, gold_answer)
    if t1_result:
        metrics.update(t1_result)
        return metrics

    # TIER 2: intermediate path (fuzzy match -> use case: typos, spelling mistakes in short ans (FR, MCQ)
    t2_result = check_fuzzy_match(player_answer, gold_answer, fuzzy_threshold)
    metrics["fuzzy_score"] = t2_result["fuzzy_score"] # Log the score regardless of pass/fail
    if t2_result["is_correct"]:
        metrics.update(t2_result)
        return metrics

    # TIER 3: Semantic matching (final resolution path)
    player_tensor = encode_player_answer(player_answer)

    # check similarity of player answer to gold answer, answer variations with helper
    correct_ans_score, matched_variation = check_semantic_variations(player_tensor,
                                                                     gold_ans_tensor,
                                                                    answer_variation_tensor_matrix)
    
    # preload base telemetry (applies to Paths A, B, C)
    metrics['telemetry'].update({
        "base_sim_score": round(correct_ans_score, 4),
        "matched_variation": matched_variation
    })
    
    # Path A: player answer meets threshold immediatetly
    if correct_ans_score >= semantic_threshold:
        metrics.update({"is_correct": True, 
                        "resolution_tier" : 'semantic'})
        return metrics

    # Path B: ambiguous range (boost score if any term matches entity_refs)
    elif correct_ans_score < semantic_threshold and correct_ans_score >= ambiguous_ans_threshold:
        
        # Initialize (prevent UnboundLocalError)
        matched_term = None
        boost_applied = 0.0
        updated_correct_ans_score = correct_ans_score
        
        for entity in entity_refs:
            # use regex with word boundaries matching entity
            pattern = r'\b' + re.escape(entity.lower()) + r'\b'
            if re.search(pattern, player_answer):
                matched_term = entity
                boost_applied = entity_boost_modifier
                updated_correct_ans_score = min(1.00, correct_ans_score + boost_applied) 
                break
            # check updated score against treshold again
        if updated_correct_ans_score >= semantic_threshold :
            metrics.update({"is_correct": True, 
                            "resolution_tier" : 'semantic_boosted'
                            })
        else:
            metrics.update({"is_correct": False, 
                           "resolution_tier" : 'failed_semantic_boosted'})
        
        metrics['telemetry'].update({
                        "boost_applied": boost_applied,
                        "matched_entity_ref" : matched_term, 
                        "final_boosted_score": round(updated_correct_ans_score, 4)
                        })
        return metrics
    
    # Path C: wrong answer (score below the ambiguous threshold)
    else:
        metrics.update({
            "is_correct": False,
            "resolution_tier": "failed_semantic"
        })
        return metrics
    
    def check_ex_answer():
        """_summary_
        """
    