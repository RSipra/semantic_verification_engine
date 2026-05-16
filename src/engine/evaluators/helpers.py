
"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) -> General Helpers for the Answer Evaluators
-----------------------------------------------------------------------


"""
from typing import Tuple
from rapidfuzz import fuzz
import torch
from sentence_transformers import util
from core.embeddings import get_sbert_model, sbert_settings

# FOR MCQ & FR Only: quick direct answer check.    
def is_exact_match(player_answer: str, correct_answer: str) -> bool:
    """ TIER 1: Exact match of player answer to Gold dataset correct answer for FR, MCQ"""
    return player_answer == correct_answer   

# FOR MCQ & FR Only: quick fuzzy answer check. 
def compute_fuzzy_match(player_answer: str, correct_answer: str) -> float:
    """TIER 2: Fuzzy match of player answer. Always returns the score for telemetry."""
    return fuzz.ratio(player_answer, correct_answer)/100    # normalized to return vals between 0 to 1.

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
