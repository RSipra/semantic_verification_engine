"""
Project: SVE (ref implementation: Harry Potter Trivia)
PHASE 2 Tracer -> Context Refinery: NLP Lab (Answer checking logic)
"""
## setup / imports
from dataclasses import dataclass, fields
from typing import List, Tuple
import pandas as pd
import numpy as np
from sentence_transformers import util
import torch
from rapidfuzz import fuzz
import regex as re
from core.embeddings import get_sbert_model, sbert_settings, get_nli_model, nli_settings

## constants and thresholds
# thresholds
FUZZY_THRESHOLD = 0.85          # 85% (normalized) character similarity (catches 1-2 letter typos)
SEMANTIC_THRESHOLD = 0.9        # SBERT cosine similarity
DISTRACTOR_DELTA = 0.30         # player answer comparison against distractors vs. correct answer
AMBIGUOUS_ANS_FLOOR = 0.60  # for enity_ref matches - lower threshold for sim score at which to check  
ENTITY_REF_MATCH_BOOST = 0.10   # sim score boost if player used a know alias or synoym (inject domain understanding to vanilla sbert) 
EX_NLI_CONFIDENCE = 0.80
EX_SBERT_FLOOR = 0.55

# loaded model from singleton cache (SBERT & NLI models defined centrally in embeddings.py)
model = get_sbert_model()
nli_model = get_nli_model()

## Structured output: Answer Evaluation Results 
# standardizing answer evaluation metrics into data classes
@dataclass
class BaseEvalResults:
    """
    Core fields shared by every single evaluation.
    Attributes:
        is_correct (bool): The final boolean result of the evaluation. Defaults to False.
        resolution_tier (str): Tracks which tier of the pipeline (e.g. 'exact', 'fuzzy', 
            'semantic', 'failed_semantic') triggered the final decision.
        fuzzy_score (float): The Tier 2 (RapidFuzz) string matching ratio 
            (normalized to be between 0 and 1).    
    """
    is_correct: bool = False
    resolution_tier: str = "unresolved" # track how many tiers of evaluation were needed to determine correctness
    fuzzy_score: float = 0.0
    
    def __post_init__(self):
        """
        Automatically rounds all float fields in this class and any 
        subclass to 4 decimal places. (AI generated)
        """
        PRECISION = 4  
        
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, float):
                setattr(self, f.name, round(value, PRECISION))

##  MCQ 

@dataclass
class MCQEvalResults(BaseEvalResults):
    """
    evaluation payload for for Multiple Choice Question evaluations.

    Attributes:
        sim_correct_ans (float): The highest cosine similarity score against 
            the gold answer or its answer_variations.
        sim_distractor (float): The highest cosine similarity score against 
            any distractor option.
        margin (float): The mathematical difference between the correct similarity 
            and the distractor similarity.
        matched_variation (bool): True if the player matched a shorthand/variation 
            better than the primary gold answer.
    """
    sim_correct_ans : float = 0.0  # track semantic similarity score with gold / correct answer
    sim_distractor: float = 0.0    # track semantic similarity score with closest distractor
    margin: float = 0.0  # diff between player-gold similarity and player-distractor similarity for semantic tier,
    matched_variation: bool = False  # whether the player answer matched a variation (shorthand) rather than the main gold answer (telemetry placeholder)

## FR
@dataclass
class FREvalResults(BaseEvalResults):
    """
    evaluation payload for Factual Recall evaluations.
    
    Stores the SBERT similarity scores and tracking flags to monitor 
    how closely players are matching the expected entities and variations.

    Attributes:
        base_sim_score (float): The raw cosine similarity score before any modifiers.
        matched_variation (bool): True if the player matched a variation better 
            than the primary gold answer.
        matched_entity_ref (str | None): The specific alias or synonym from the 
            semantic_entity_refs column that triggered the boost, if any.
        boost_applied (float): The value of any domain-specific boost applied 
            (e.g. matching a known alias/synonym from the semantic_entity_refs column)
        final_boosted_score (float): The final calculated score (base_sim_score + boost_applied)
    """
    base_sim_score: float = 0.0      # vs. ans and ans variations
    matched_variation: bool = False  # flag if player answer matched variation instead of main answer
    matched_entity_ref: str | None = None     # alias / synonym matched from semantic_entity_refs col
    boost_applied: float = 0.0       # entitry ref boost for ambiguous similarity scores
    final_boosted_score: float = 0.0 # base_sim_score + boost_applied

## EX
@dataclass
class EXEvalResults(BaseEvalResults):
    """
    evaluation payload for Explanation (long narrative) evaluations.
    Stores primary SBERT and ambiguous NLI results.

    Attributes:
        primary_similarity_score (float): The highest cosine similarity achieved against the 
            narrative evaluators (Gold Answer + Variations).
        matched_variation (bool): returns True if the player answer matched most closely to
            a variation (instead of the main `answer`)
        nli_label: label assigned by NLI model (entailment, contradiction, or neutral)
        nli_confidence: numerical certainty score by NLI model (0 to 1)
    """
    primary_similarity_score: float = 0.0
    matched_ans_variation: bool = False
    nli_label: str = ""
    nli_confidence: float = 0.0       

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
def _is_exact_match(player_answer: str, correct_answer: str) -> bool:
    """ TIER 1: Exact match of player answer to Gold dataset correct answer for FR, MCQ"""
    return player_answer == correct_answer   

# FOR MCQ & FR Only: quick fuzzy answer check. 
def _is_fuzzy_match(player_answer: str, correct_answer: str) -> float:
    """TIER 2: Fuzzy match of player answer. Always returns the score for telemetry."""
    return fuzz.ratio(player_answer, correct_answer)/100    # normalized to return vals between 0 to 1.

# central helper for all question types for encoding player answers for semantic checks
def _encode_player_answer(player_answer: str) -> torch.Tensor:
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
def _check_semantic_variations(player_answer_tensor: torch.Tensor,
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
                     fuzzy_threshold: float = FUZZY_THRESHOLD,
                     semantic_threshold: float = SEMANTIC_THRESHOLD,
                     distractor_delta: float = DISTRACTOR_DELTA) -> MCQEvalResults:
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
        MCQEvalResults: A strictly typed payload containing the verification results 
            and nested telemetry.
    """
    # confirm preprocessing in place
    assert player_answer == player_answer.lower(), "CRITICAL: player_answer must be lowercased before reaching the MCQ checker." 
    # normalization of player ans is handled upstream of question_type speciifc helper
    
    # initialize mcq results instance
    result = MCQEvalResults()
    
    # TIER 1: fast path (exact match) --> use case: perfect answers 
    if _is_exact_match(player_answer, gold_answer):
        # update and return results 
        result.is_correct = True
        result.resolution_tier = 'exact'
        result.fuzzy_score = 100
        return result
    
    # TIER 2: intermediate path (fuzzy match -> use case: typos, spelling mistakes in short ans (FR, MCQ)
    result.fuzzy_score = round(_is_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "fuzzy"
        return result

    # TIER 3: semantic logic (resolution path)
    # 1. encode player answer using helper
    player_tensor = _encode_player_answer(player_answer)
    
    # 2. calculate similarity scores (against main gold correct answer, answer variations and find most similar) with helper
    correct_ans_score, matched_variation = _check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)
    
    # 2.2: difference to distractors
    # For the matrix [N, 384], cos_sim returns [1, N]. [0] gets the vector of scores.
    distractor_scores = util.cos_sim(player_tensor, distractor_tensor_matrix)[0]
    max_dist_score = torch.max(distractor_scores).item()
    
    margin = correct_ans_score - max_dist_score
    
    # 3. update results telemetry metrics
    result.sim_correct_ans = round(correct_ans_score, 4)
    result.sim_distractor = round(max_dist_score, 4)
    result.margin =  round(margin, 4)
    result.matched_variation =  matched_variation # True if a variation (likely shorthand used)
    
    if correct_ans_score >= semantic_threshold and margin >= distractor_delta:
        result.is_correct= True
        result.resolution_tier=  "passed_semantic"
    else:
        result.is_correct = False
        result.resolution_tier = "failed_semantic"
    
    return result

### 2.2 FR (Factual Recall)
def check_fr_answer(player_answer: str, 
                    gold_answer: str,
                    entity_refs: List[str],
                    gold_ans_tensor: torch.Tensor,
                    answer_variation_tensor_matrix: torch.Tensor, 
                    fuzzy_threshold: float = FUZZY_THRESHOLD,
                    semantic_threshold: float = SEMANTIC_THRESHOLD,
                    ambiguous_cutoff: float = AMBIGUOUS_ANS_FLOOR,
                    entity_boost_modifier: float = ENTITY_REF_MATCH_BOOST) -> FREvalResults:
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
        FREvalResults: A strictly typed payload containing the verification results 
            and nested telemetry
    """
    # confirm preprocessing in place
    assert player_answer == player_answer.lower(), "CRITICAL: player_answer must be lowercased before reaching the FR checker." 
    
    # initialze FR metrics results object
    result = FREvalResults()
    
    # TIER 1: fast path (exact match) --> use case: perfect answers
    if _is_exact_match(player_answer, gold_answer):
        result.is_correct = True
        result.resolution_tier = 'exact'
        result.fuzzy_score = 100
        return result

    # TIER 2: intermediate path (fuzzy match -> use case: typos, spelling mistakes in short ans (FR, MCQ)
    result.fuzzy_score = round(_is_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "fuzzy"
        return result

    # TIER 3: Semantic matching (final resolution path)
    player_tensor = _encode_player_answer(player_answer)

    # check similarity of player answer to gold answer, answer variations with helper
    correct_ans_score, matched_variation = _check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)
    
    # preload base telemetry (applies to Paths A, B, C)
    result.base_sim_score = round(correct_ans_score, 4)
    result.matched_variation = matched_variation
    
    # Path A: player answer meets threshold immediatetly
    if correct_ans_score >= semantic_threshold:
        result.is_correct = True
        result.resolution_tier = 'passed_primary_semantic'
        return result

    # Path B: ambiguous range (boost score if any term matches entity_refs)
    elif correct_ans_score < semantic_threshold and correct_ans_score >= ambiguous_cutoff:
        
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
            result.is_correct = True
            result.resolution_tier = 'passed_semantic_boosted'
        else:
            result.is_correct = False
            result.resolution_tier = 'failed_semantic_boosted'
        
        # update common telemetry
        result.boost_applied = boost_applied
        result.matched_entity_ref = matched_term
        result.final_boosted_score = round(updated_correct_ans_score, 4)
        return result
    
    # Path C: wrong answer (score below the ambiguous threshold)
    else:
        result.is_correct = False
        result.resolution_tier = "failed_semantic"
        return result

### 2.3 EX (Explanatory) 
# coverage check of player answer prior to NLI judge
def _calculate_coverage_ratio(player_answer:str, 
                              target_list: List[str]):
    """
    Calculates the percentage of target words/phrases found in the text 
    using strict Regex word boundaries.
    """
    if not target_list:
        return 1.0  # continue with analysis if no target list
    found_count = 0
    valid_targets = 0

    for term in target_list:
        if not term:
            continue
        valid_targets+=1
        pattern = r'\b' + re.escape(term) + r'\b'
        if re.search(pattern, player_answer):
            found_count += 1

    if valid_targets == 0:
        return 1.0
    return found_count / valid_targets        

# nli evaluation of answer if sbert ambiguous
# Assuming: from sentence_transformers import CrossEncoder
# nli_model = CrossEncoder('cross-encoder/nli-deberta-v3-small')

def _check_nli_entailment(premise: str, hypothesis: str, nli_model) -> tuple[bool, str, float]:
    """
    Evaluates logical entailment between a gold answer (premise) and player answer (hypothesis).
    Returns: (is_entailed: bool, predicted_label: str, confidence_score: float)
    """
    # 1. run NLI cross-encoder
    scores = nli_model.predict([(premise, hypothesis)])[0]

    # 2. convert logits to probabilities using softmax (optional, but good for telemetry)
    probabilities = np.exp(scores) / np.sum(np.exp(scores))

    # 3. get winning id (cast to native int for dict lookup)
    predicted_class_id = np.argmax(probabilities).item()
    confidence = probabilities[predicted_class_id]

    # 4. map id to label using our SOT nli from settings.py
    predicted_label = nli_settings.label_mapping.get(predicted_class_id, "unknown")
    
    # 5. determine success (only if tag is 'entailed')
    is_entailed = (predicted_label == "entailment")
    
    return is_entailed, predicted_label, float(confidence)

# main EX evaluator   
def check_ex_answer(player_answer: str,
                    gold_answer: str,
                    gold_ans_tensor: torch.Tensor,
                    answer_variation_tensor_matrix: torch.Tensor,
                    fuzzy_threshold: float = FUZZY_THRESHOLD,
                    semantic_threshold: float = SEMANTIC_THRESHOLD,
                    ambiguous_cutoff: float = AMBIGUOUS_ANS_FLOOR,
                    nli_confidence_threshold: float = EX_NLI_CONFIDENCE,
                    sbert_floor: float = EX_SBERT_FLOOR) -> EXEvalResults:
    """_summary_
    """
    # confirm preprocessing in place
    assert player_answer == player_answer.lower(), "CRITICAL: player_answer must be lowercased before reaching the FR checker." 
    
    # initialze EX metrics results object
    result = EXEvalResults()
    
    # Tier 1, 2: any quick wins with exact, fuzzy:
    if _is_exact_match(player_answer, gold_answer):
        result.is_correct = True
        result.resolution_tier = 'exact'
        result.fuzzy_score = 100
        return result

    result.fuzzy_score = round(_is_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "fuzzy"
        return result

    # Tier 3: semantic resolution
    player_tensor = _encode_player_answer(player_answer)

    # check similarity of player answer to gold answer, answer variations
    correct_ans_score, matched_variation = _check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)

    # preload base telemetry (applies to Paths A, B, C)
    result.primary_similarity_score = round(correct_ans_score, 4)
    result.matched_ans_variation = matched_variation

    # Path A: player answer meets threshold immediatetly
    if correct_ans_score >= semantic_threshold:
        result.is_correct = True
        result.resolution_tier = 'primary_semantic'
        return result

    # Path B: ambiguous resolution with coverage, NLI judge
    elif correct_ans_score < semantic_threshold and correct_ans_score >= ambiguous_cutoff:

        # use a cross-encoder NLI judge to score ambiguous answer
        _, nli_label, nli_confidence = _check_nli_entailment(
            premise=gold_answer,
            hypothesis=player_answer,
            nli_model=nli_model
        )
        # append NLI telemetry to your result object
        result.nli_label = nli_label
        result.nli_confidence = round(nli_confidence, 4)

        if nli_label == 'entailment' and result.primary_similarity_score >= sbert_floor:
            result.is_correct = True
            result.resolution_tier = 'nli_entailment_pass'
        
        elif nli_label == 'neutral' and result.nli_confidence >= nli_confidence_threshold:
            if result.primary_similarity_score >= sbert_floor:
                result.is_correct = True
                result.resolution_tier = 'nli_neutral_lore_pass'
            else:
                result.is_correct = False
                result.resolution_tier = 'nli_fail_vague_neutral' 
            
        else:
            # nli logic failure (contradiction or neutral)
            result.is_correct = False
            result.resolution_tier = f'nli_failed_{nli_label}'
        
        return result

        # TODO Path B.3: SLM resolution in future (optional) if false negatives high

    # Path C: completely wrong answer (below ambiguous lower-bound threshold)
    else:
        result.is_correct = False
        result.resolution_tier = 'primary_semantic_fail'
        return result
