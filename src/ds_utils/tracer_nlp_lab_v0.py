"""
Project: SVE (ref implementation: Harry Potter Trivia)
PHASE 2 Tracer -> Context Refinery: NLP Lab (Answer checking logic)
"""
## setup / imports
import time
from datetime import date
from functools import wraps
import os
from dataclasses import dataclass, fields
from typing import List, Tuple
import pandas as pd
import numpy as np
from sentence_transformers import util
import torch
from rapidfuzz import fuzz
import regex as re
from dateparser.search import search_dates
from word2number import w2n
from pydantic import BaseModel, Field

from dotenv import load_dotenv, find_dotenv
import google.generativeai as genai
from core.embeddings import get_sbert_model, sbert_settings, get_nli_model, nli_settings
from ds_utils.tracer_descp_features_v0 import count_clean_words
from ds_utils.ds_constants import AnswerType

# --configure API for LLM judge for EX evaluator--
load_dotenv(find_dotenv("config.env"), override=True)
google_api_key = os.environ.get('GEMINI_API_KEY')
if not google_api_key:
    raise ValueError("Error: GOOGLE_API_KEY not found.")
genai.configure(api_key=google_api_key)  # type: ignore

## constants and thresholds
# thresholds
FUZZY_THRESHOLD = 0.85          # 85% (normalized) character similarity (catches 1-2 letter typos)
SEMANTIC_THRESHOLD = 0.9        # SBERT cosine similarity
DISTRACTOR_DELTA = 0.30         # player answer comparison against distractors vs. correct answer
AMBIGUOUS_ANS_FLOOR = 0.60  # for enity_ref matches - lower threshold for sim score at which to check  
ENTITY_REF_MATCH_BOOST = 0.10   # sim score boost if player used a know alias or synoym (inject domain understanding to vanilla sbert) 
EX_NLI_CONFIDENCE = 0.80
EX_SBERT_FLOOR = 0.55
FR_OUTLIER_THRESHOLD = 6        # outlier wordcount of FR answers in legacy dataset (q3+1.5*IQR)

HOLIDAY_MAP ={
    "halloween":"october 31",
    "valentines day": "february 14",
    "valentine's day": "february 14",
    "christmas": "december 25",
    "christmas eve": "december 24",
    "new years eve": "december 31",
    "new year's eve": "december 31"
}

# loaded model from singleton cache (SBERT & NLI models defined centrally in embeddings.py)
model = get_sbert_model()
nli_model = get_nli_model()

# LLM models to use for API calls
PRIMARY_MODEL = "models/gemini-3.1-flash-lite-preview"
FALLBACK_MODEL = "models/gemini-flash-latest"   

## LLM calls helpers and method

# system prompt for EX (explantory questions) LLM judge
SYSTEM_PROMPT_EX = """
You are an objective Logic Validator for a trivia system.
Your task is to determine if the Player's Guess semantically entails the causal logic and core meaning of the Ground Truth Context.

EVALUATION RULES:
1. DIRECTIONALITY & CAUSALITY: Strictly check the active/passive flow. If the player inverts the subject and the object (e.g., "A caused B" instead of "B caused A"), it is INCORRECT.
2. THEMATIC ADJACENCY IS NOT EQUIVALENCE: Do not pass answers that are merely in the same thematic neighborhood (e.g., "fearing" a concept is not the same as "understanding" it). The core logical meaning must align.
3. CONTEXTUAL INTENT & PRONOUNS: If a player uses vague pronouns (e.g., "he", "it", "they") or partial explanations, you may evaluate them as CORRECT only if the context of their answer makes their logical intent undeniable. Do not penalize conversational shorthand if the causal meaning is clear.
4. FORGIVENESS OF STRUCTURE & OMISSIONS: Accept typos, passive voice (e.g., evaluating "Action B was performed by Entity A" as equivalent to "Entity A performed Action B"), and partial explanations, provided the core causal action is present and not contradicted. If a player omits a minor detail but captures the main action, do NOT penalize them.
5. CRITICAL ANTI-RECITATION RULE: You must write your `reasoning` and `mc_dialogue` using your own original phrasing. Do not quote the source material directly.

Chain of Thought Directive:
In your `reasoning` field, objectively map the causal logic and flow of the Player's Guess against the Ground Truth. If there is a causal inversion, missing core entity, or thematic mismatch, you must evaluate `is_correct` as false.

In your `mc_dialogue` field, act as an engaging, sympathetic trivia host reacting to the player's attempt.
"""

# system prompt for EX (explantory questions) LLM judge
SYSTEM_PROMPT_FR_SPECIALIST = """
You are an objective Data Validator for a trivia system. 
Your task is to verify if the Player Guess contains the factual entities required by the Ground Truth Context.

EVALUATION RULES:
1. STRICT PROPER NOUN IDENTITY: If the ground truth requires a specific named entity (e.g., 'Ron Weasley', 'Purge & Dowse'), the player must provide that specific entity. 'Percy Weasley' or a broad answer like 'London' is a FATAL MISMATCH.
2. SEMANTIC EQUIVALENCE FOR ACTIONS/DESCRIPTORS: You MUST accept synonyms, paraphrasing, and alternate framings for non-proper nouns. (e.g., "not losing appendages" is semantically equivalent to "keeping remaining limbs"). Do not penalize grammatical framing.
3. FLUFF NEUTRALITY: Ignore conversational intros, extra lore, and subjective adjectives (e.g., 'nerdy and annoying') as long as the core required entities are present and accurate.

Chain of Thought Directive:
In your `reasoning` field, first check for Proper Noun identity. If the specific names/places match, or if the core concepts are semantically equivalent, you must evaluate `is_correct` as true.
"""    

# LLM response pydantic model (EX, FR)
class LLMJudgeResponse(BaseModel):
    """
    """
    # push model to think before assigning boolean
    reasoning: str = Field(description="Step-by-step logical proof of why the answer fails or passes the strict criteria.")
    mc_dialogue: str = Field(description="A short, 1-sentence in-character reaction from the quiz host.")
    # The boolean comes LAST, after the logic is established
    is_correct: bool = Field(description="True ONLY if the reasoning proves absolute semantic and entity alignment.")
# decorator for timing llm calls
def track_eval_latency(func):
    """
    A decorator that intercepts the execution of an evaluator function,
    calculates the total latency, and dynamically injects it into the 
    returned EXEvalResults object.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        
        # Execute the main function (this runs all your Tier 1-4 logic)
        result = func(*args, **kwargs)
        
        # Calculate latency and inject it before returning to the Tracer loop
        latency = time.perf_counter() - start_time
        result.execution_time_sec = round(latency, 4)
        
        return result
    return wrapper

def _build_prompt_context(gold_answer: str, 
                          answer_variations: list, 
                          explanation: str, 
                          source_quote: str) -> str:
    """
    Dynamically constructs the ground truth context block for the LLM judge.

    This helper function aggregates the definitive answers, acceptable aliases, 
    and lore explanations into a strictly formatted string. It optimizes the prompt 
    by conditionally injecting the exact source text quote only if it is available 
    (e.g., from the synthetic generation pipeline), gracefully falling back to the 
    detailed explanation for legacy dataset entries.

    Args:
        gold_answer (str): The primary correct answer string from the dataset.
        answer_variations (list): A list of acceptable canonical alternate answers.
        explanation (str): The detailed lore explanation of why the answer is correct.
        source_quote (str): The canonical text quote verifying the answer. Handled safely 
                            if missing (e.g., evaluates to Pandas NaN or literal "<NA>").

    Returns:
        str: A formatted context block designed to be injected directly into the user prompt.
    """ 
    # base context for every question evaluation
    context = f"""
    [GROUND TRUTH CONTEXT]
    Gold Answer: {gold_answer}
    Acceptable Variations: {', '.join(answer_variations)}
    Explanation: {explanation}
    """
    # conditionally append the quote only if it exists (for synthetic data)
    if pd.notna(source_quote) and source_quote.strip() != "<NA>":
        context += f'    Source Text Quote: "{source_quote}"\n'
        
    return context

def _call_llm_judge(question: str, 
                    gold_answer: str, 
                    player_answer: str,
                    answer_variations: list,
                    source_quote: str,
                    explanation: str,
                    system_prompt: str) -> LLMJudgeResponse:
    """
    Generalized LLM caller that handles both EX (Logic) and FR (Entity) 
    evaluation based on the passed system_prompt.
    """
    # 1. configuration for resilience 
    model_cascade = [PRIMARY_MODEL, FALLBACK_MODEL]
    
    user_prompt = f"""
    [EVALUATION TASK]
    Question: {question}
    Player Guess: {player_answer}
    
    {_build_prompt_context(gold_answer, answer_variations, explanation, source_quote)}           
    """

    for target_model in model_cascade:
        try:
            # initialize the Gemma model
            model = genai.GenerativeModel( #  type: ignore
                model_name=target_model, 
                system_instruction=system_prompt
            )
            print("--- Escalating to LLM Judge ---")
            start_time = time.time()
            response = model.generate_content(
                user_prompt,
                generation_config=genai.GenerationConfig(  # type: ignore
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=LLMJudgeResponse, ),
                request_options={"timeout": 200.0}
            )
            end_time = time.time()
            print(f"LLM resolution time: {round(end_time - start_time, 2)} seconds")
            # 2. conservative rate Limiting (10 RPM / 6s buffer)
            time.sleep(6.0)
            
            # clean markdown formatting before parsing
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            # 3. validation    
            return LLMJudgeResponse.model_validate_json(raw_text.strip())

        except Exception as e:
            print(f"\n⚠️ API CRASH/TIMEOUT for Question: {question}")
            print(f"Error Details: {str(e)}\n")
            error_msg = str(e)
            if "429" in error_msg or "404" in error_msg:
                print(f"⚠️ {target_model} failed ({error_msg[:20]})... Attempting fallback.")
                time.sleep(2.0)
                continue
            time.sleep(4.0) # sleep even on errors to cool down the connection
            
            return LLMJudgeResponse(
                is_correct=False,
                mc_dialogue="The Restricted Section is currently off-limits.",
                reasoning=f"System error: {str(e)}"
            )
    # 4. Graceful Degradation if entire cascade fails
    return LLMJudgeResponse(
        is_correct=False,
        mc_dialogue="The Floo Network is currently congested.",
        reasoning="System error: All LLM tiers failed or exceeded quota."
    )        
    

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
    llm_mc_response: str = ""
    llm_reasoning: str = ""
    execution_time_sec: float = 0.0

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
    llm_mc_response: str = ""
    llm_reasoning: str = ""
    execution_time_sec: float = 0.0

## --- 1. DATASET PREPROCESSING ---

## 1.1 player answer processing



## 1.2: Add tensors for embedding columns

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

### --- 2. TEXT ANSWERS ---
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

@track_eval_latency
def check_fr_answer(question: str, 
                    player_answer: str, 
                    gold_answer: str,
                    gold_answer_word_count: int,
                    answer_variations: List[str],
                    source_quote: str,
                    explanation: str,
                    entity_refs: List[str],
                    gold_ans_tensor: torch.Tensor,
                    answer_variation_tensor_matrix: torch.Tensor, 
                    fuzzy_threshold: float = FUZZY_THRESHOLD,
                    semantic_threshold: float = SEMANTIC_THRESHOLD,
                    ambiguous_cutoff: float = AMBIGUOUS_ANS_FLOOR,
                    entity_boost_modifier: float = ENTITY_REF_MATCH_BOOST,
                    enable_llm_escalation: bool = False  #for notebook experiments only
                    ) -> FREvalResults:
    """
    Evaluates a player's Factual Recall (open-text) answer using a 3-Tier logic.
    
    Because FR lacks the safety net of MCQ distractors, this function utilizes a stricter 
    baseline semantic threshold combined with a *entity boost*. It mathematically 
    rescues ambiguous SBERT scores by dynamically injecting domain knowledge (proper nouns) 
    before failing the player.

    The 4 Tiers of Evaluation:
    --------------------------
    - Tier 1 (Exact): Instant pass for perfect string matches (O(1) fast path).
    - Tier 2 (Fuzzy): Levenshtein distance check to catch minor typos.
    - Tier 3 (Semantic & Entity): SBERT cosine similarity check against the Gold Answer 
      and acceptable variations. Dynamically injects a score boost if core proper nouns match.
    - Tier 4 (LLM Specialist): If the player's answer is a statistical length outlier 
      (indicating conversational fluff or lore-dumping), it bypasses Tier 3 and hits 
      a strict LLM Entity Auditor to prevent semantic dilution.
      
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
    
    # initialize FR metrics results object
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
    
    # Path A: check player answer lengths (if outlier or if too verbose)
    player_ans_wc = count_clean_words(player_answer)
    
    # edge cases routing to LLM judge
    is_outlier = player_ans_wc > FR_OUTLIER_THRESHOLD   # exceeds legacy outlier ans word count
    # verbose player ans: if twice the len of expected and wc in vector dilution range of sbert
    is_disproportionate = (player_ans_wc >= 2 * gold_answer_word_count) and (player_ans_wc >= 8) 
        
    if enable_llm_escalation and (is_outlier or is_disproportionate):
        llm_judgment = _call_llm_judge(question,
                                   gold_answer, 
                                   player_answer,
                                   answer_variations,
                                   source_quote,
                                   explanation,
                                   SYSTEM_PROMPT_FR_SPECIALIST)
    
        if llm_judgment.is_correct:
            result.is_correct = True
            result.resolution_tier = 'llm_judge_pass'
        else:
            result.is_correct = False
            result.resolution_tier = 'llm_judge_fail' 
        # update llm metrics    
        result.llm_mc_response = llm_judgment.mc_dialogue
        result.llm_reasoning = llm_judgment.reasoning          
        return result
            
    # Path B: player answer meets threshold immediatetly
    elif correct_ans_score >= semantic_threshold:
        result.is_correct = True
        result.resolution_tier = 'passed_primary_semantic'
        return result

    # Path C: ambiguous range (boost score if any term matches entity_refs)
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
    
    # Path D: wrong answer (score below the ambiguous threshold)
    else:
        result.is_correct = False
        result.resolution_tier = "failed_semantic"
        return result

### 2.3 EX (Explanatory) 

# nli evaluation of answer if sbert ambiguous
# Assuming: from sentence_transformers import CrossEncoder
# nli_model = CrossEncoder('cross-encoder/nli-deberta-v3-small')
def _check_nli_entailment(premise: str, hypothesis: str, nli_model_inst) -> tuple[bool, str, float]:
    """
    Evaluates logical entailment between a gold answer (premise) and player answer (hypothesis).
    Returns: (is_entailed: bool, predicted_label: str, confidence_score: float)
    """
    # 1. run NLI cross-encoder
    scores = nli_model_inst.predict([(premise, hypothesis)])[0]

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

# MAIN EX Evaluator 
@track_eval_latency  
def check_ex_answer(question: str,
                    player_answer: str,
                    gold_answer: str,
                    gold_answer_wordcount: int,
                    gold_ans_tensor: torch.Tensor,
                    answer_variations: List[str],
                    source_quote: str,
                    explanation: str,
                    answer_variation_tensor_matrix: torch.Tensor,
                    fuzzy_threshold: float = FUZZY_THRESHOLD,
                    semantic_threshold: float = SEMANTIC_THRESHOLD,
                    ambiguous_cutoff: float = AMBIGUOUS_ANS_FLOOR,
                    enable_llm_escalation: bool = True,  #for notebook experiments only
                    enable_nli_escalation:bool = False  #for notebook experiments only
                    ) -> EXEvalResults:
    """
    Evaluates explanatory (EX) trivia answers through a multi-tier NLP routing matrix.

    This function optimizes compute by resolving simple matches locally and only
    escalating complex logical or lore-based abstractions to an external language 
    model API. For the current Tracer iteration, this utilizes Gemma 4 via Vertex AI 
    (zero-cost open-weights), but the routing architecture is modular to support 
    interchangeable SLMs/LLMs in future development.

    Args:
        question (str): The trivia question prompt.
        player_answer (str): The raw string input provided by the user.
        gold_answer (str): The primary correct answer string from the dataset.
        gold_answer_wordcount (int): Precomputed word count of the gold answer.
        gold_ans_tensor (torch.Tensor): Pre-encoded SBERT embeddings for the gold answer.
        answer_variations (List[str]): List of acceptable alternate answer strings.
        source_quote (str): The canonical text quote verifying the answer (if synthetic).
        explanation (str): The detailed lore explanation of why the answer is correct.
        answer_variation_tensor_matrix (torch.Tensor): Matrix of embeddings for acceptable alternate answers.
        fuzzy_threshold (float): Minimum score for a Tier 2 deterministic fuzzy pass.
        semantic_threshold (float): Minimum SBERT score required before NLI entailment can auto-pass.
        ambiguous_cutoff (float): The floor for SBERT scores; answers below this fail unless verbosity bypass is triggered.
        enable_llm_escalation (bool): Toggle to activate/deactivate the Tier 4 LLM judge for A/B testing.

    Returns:
        EXEvalResults: A populated telemetry object containing the final boolean judgment (`is_correct`), 
                       the exact pipeline exit node (`resolution_tier`), and internal NLP scores.

    Routing Flow:
        - Tier 1/2: O(1) Exact and Fuzzy string matching.
        - Tier 3.1: SBERT vector similarity (filters vocabulary mismatches, features Verbosity Bypass).
        - Tier 3.2: NLI Cross-Encoder (gates inverted logic and contradictions).
        - Tier 4: LLM Judge escalation for the "Messy Middle" (vague abstractions/deep lore).
    """
    # confirm preprocessing in place
    assert player_answer == player_answer.lower(), "CRITICAL: player_answer must be lowercased before reaching the EX checker." 
    
    # initialize EX metrics results object
    result = EXEvalResults()
    
    # TIER -1: exact match, grab any O(1) wins
    if _is_exact_match(player_answer, gold_answer):
        result.is_correct = True
        result.resolution_tier = 'exact'
        result.fuzzy_score = 100
        return result
    # TIER-2: fuzzy match, grab any O(1) wins
    result.fuzzy_score = round(_is_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "fuzzy"
        return result

    # TIER-3: semantic resolution (SBERT + NLI)
    player_tensor = _encode_player_answer(player_answer)
    # check similarity of player answer to gold answer, answer variations
    correct_ans_score, matched_variation = _check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)
    # preload base telemetry 
    result.primary_similarity_score = round(correct_ans_score, 4)
    result.matched_ans_variation = matched_variation
    
    player_answer_wordcount = count_clean_words(player_answer)
    len_ratio = player_answer_wordcount / max(1, gold_answer_wordcount)

    # Tier 3.1: primary semantic check
    # verbosity bypass to the LLM
    if correct_ans_score < ambiguous_cutoff:
        if len_ratio >= 2.0 and enable_llm_escalation:
            llm_judgment = _call_llm_judge(question, 
                                           gold_answer, 
                                           player_answer,
                                           answer_variations, 
                                           source_quote, 
                                           explanation,
                                           SYSTEM_PROMPT_EX) 
            if llm_judgment.is_correct:
                result.is_correct = True
                result.resolution_tier = 'llm_judge_long_ans_pass'           
            else:
                result.is_correct = False
                result.resolution_tier = 'llm_judge_long_ans_fail'
            # return llm metrics for both cases
            result.llm_mc_response = llm_judgment.mc_dialogue
            result.llm_reasoning = llm_judgment.reasoning
            return result
        else:
            result.is_correct = False
            result.resolution_tier = 'primary_semantic_fail'
            return result
        
    # Tier 3.2: NLI cross-encoder labelling (logic check)
    if enable_nli_escalation:
        _, nli_label, nli_confidence = _check_nli_entailment(
                premise=gold_answer,
                hypothesis=player_answer,
                nli_model_inst=nli_model
            )
        # append NLI telemetry to your result object
        result.nli_label = nli_label
        result.nli_confidence = round(nli_confidence, 4)

        # contradiction fail fast
        if nli_label == 'contradiction':
            result.is_correct = False
            result.resolution_tier = 'nli_contradiction_fail'
            return result

        # entailment pass (high vocab, high directional logic)
        if nli_label == 'entailment' and result.primary_similarity_score >= semantic_threshold:
            result.is_correct = True
            result.resolution_tier = 'nli_entailment_pass'
            return result

    # Tier 4: LLM resolution for remaining cases
    #         all 'neutral' AND 'entailment' with ambiguous sbert scores 
    #         (i.e. semantic_threshold < sbert_score <= ambiguous_cutoff)
    
    # notebook experiment LLM bypass: If toggle is off, fail ambiguous answers locally
    if not enable_llm_escalation:
        result.is_correct = False
        result.resolution_tier = 'ambiguous_fail_without_LLM'
        return result
    
    llm_judgment = _call_llm_judge(question, 
                                   gold_answer, 
                                   player_answer,
                                   answer_variations, 
                                   source_quote, 
                                   explanation,
                                   SYSTEM_PROMPT_EX)
    
    if llm_judgment.is_correct:
        result.is_correct = True
        result.resolution_tier = 'llm_judge_pass'
    else:
        result.is_correct = False
        result.resolution_tier = 'llm_judge_fail' 
    # update llm metrics    
    result.llm_mc_response = llm_judgment.mc_dialogue
    result.llm_reasoning = llm_judgment.reasoning          
    return result

# Ex test helper
def run_ex_evaluation_suite(test_suite: dict, 
                            runtime_df: pd.DataFrame, 
                            fuzzy_threshold: float = 0.95,
                            semantic_threshold: float = 0.80,
                            ambiguous_cutoff: float = 0.40,
                            use_llm: bool = False,
                            use_nli: bool = False):
    """
    Executes a suite of player answers against the EX Evaluator and tracks telemetry.
    Returns a dictionary of failed cases for easy debugging in Jupyter.
    """
    
    print(f"🚀 Starting EX Evaluation Suite (LLM Enabled: {use_llm})\n" + "-"*50)
    
    total_cases = 0
    pass_count = 0
    llm_escalation_count = 0
    llm_pass_count = 0
    
    total_execution_time = 0.0
    total_local_time = 0.0
    total_llm_time = 0.0
    
    evaluation_logs = {"passed": [], "failed": []}
    i = 1

    for q_id, q_data in test_suite.items():
        
        # 1. Extract the ground truth constants
        question_text = q_data['question']
        gold_answer_str = q_data['gold_answer'].lower().strip()
        answer_variations_list = q_data['answer_variations']
        source_quote_str = q_data['source_quote']
        explanation_str = q_data['explanation']
        
        # 2. Retrieve tensor/length data from the runtime DataFrame
        question_data = runtime_df[runtime_df['master_id'] == q_id].iloc[0]
        gold_ans_wc = question_data['answer_length']
        gold_ex_tensor = question_data['answer_embeddings_tensor']
        ex_ans_var_tensor = question_data['answer_variations_embeddings_tensor_matrix']
        
        # 3. Iterate through every player guess
        for case in q_data['test_cases']:
            total_cases += 1
            current_player_answer = case['player_answer'].lower().strip() 
            expected_outcome = case['expected']

            print(f"  -> Testing: '{current_player_answer}'")
            
            # Run through the EX checker
            result_ex = check_ex_answer(
                question=question_text,
                player_answer=current_player_answer,
                gold_answer=gold_answer_str,
                gold_answer_wordcount=gold_ans_wc,
                gold_ans_tensor=gold_ex_tensor,
                answer_variations=answer_variations_list,
                source_quote=source_quote_str,
                explanation=explanation_str,
                answer_variation_tensor_matrix=ex_ans_var_tensor,
                fuzzy_threshold=fuzzy_threshold,
                semantic_threshold=semantic_threshold,
                ambiguous_cutoff=ambiguous_cutoff,
                enable_llm_escalation=use_llm,
                enable_nli_escalation=use_nli
            )
            
            # 4. Process Results
            actual_result = "correct" if result_ex.is_correct else "incorrect"
            status = "✅ PASS" if actual_result == expected_outcome else "❌ FAIL"
            
            # Build the log entry
            log_entry = {
                'q_id': q_id,
                'player_answer': current_player_answer,
                'expected': expected_outcome,
                'got': actual_result,
                'telemetry': result_ex
            }
            if status == "✅ PASS":
                pass_count += 1
                evaluation_logs["passed"].append(log_entry)
            else:
                evaluation_logs["failed"].append(log_entry)
            
            case_time = float(result_ex.execution_time_sec)
            total_execution_time += case_time
            
            if "llm_judge" in result_ex.resolution_tier:
                total_llm_time += case_time
                llm_escalation_count += 1
                if status == "✅ PASS":
                    llm_pass_count += 1
            else:
                total_local_time += case_time          
                
            print(f"{i}. {status}: QID {q_id} | Expected: {expected_outcome} | Got: {actual_result}")
            print(f"Tier: {result_ex.resolution_tier} | Time: {result_ex.execution_time_sec}s\n")
            i += 1
            
    # 5. Generate Summary
    pass_percentage = (pass_count / total_cases) * 100 if total_cases > 0 else 0
    llm_percentage = (llm_escalation_count / total_cases) * 100 if total_cases > 0 else 0
    llm_accuracy = (llm_pass_count / llm_escalation_count) * 100 if llm_escalation_count > 0 else 0
    
    # Calculate Latency Averages
    avg_total_time = total_execution_time / total_cases if total_cases > 0 else 0
    local_cases = total_cases - llm_escalation_count
    avg_local_time = total_local_time / local_cases if local_cases > 0 else 0
    avg_llm_time = total_llm_time / llm_escalation_count if llm_escalation_count > 0 else 0

    print("="*50)
    print("📊 EX TEST SUITE SUMMARY")
    print("="*50)
    print(f"Total test cases:     {total_cases}")
    print(f"Cases that passed:    {pass_count} ({pass_percentage:.2f}%)")
    print(f"Cases that failed:    {total_cases - pass_count} ({100 - pass_percentage:.2f}%)")
    print("-" * 50)
    print(f"Avg Overall Latency:  {avg_total_time:.4f}s")
    print(f"Avg Local Latency:    {avg_local_time * 1000:.2f}ms (SBERT/NLI path)") # Converted to ms
    print(f"Avg LLM Latency:      {avg_llm_time:.2f}s (Escalation path)")
    print("-" * 50)
    print(f"LLM Escalations:      {llm_escalation_count} ({llm_percentage:.2f}% of total traffic)")  
    print(f"LLM Accuracy:         {llm_pass_count}/{llm_escalation_count} ({llm_accuracy:.2f}%)") 
    
    return evaluation_logs

## --- 3. NON-TEXT ANSWERS ---

## 3.1 Numeric answers (number, year)

def _normalize_numeric_text(raw_answer:str):
    """
    Shared helper to clean and translate numeric or year strings 
    for both player answers and gold dataset answers.
    """
    return str(raw_answer).lower().strip().replace("-", " ").replace(",", "")

def _preprocess_numeric_player_ans(raw_player_ans:str, hard_cap:int = 1):
    """
    Sanitizes raw player text into a single integer.
    Enforces an anti-hedging hard cap of 1.
    Returns None if hedging is detected or no valid number is found.
    """
    # 1. normalize answer (strip white space, any 1000 comma separater)
    ans_text = _normalize_numeric_text(raw_player_ans)

    # 2. extract numbers from surrounding text -> e.g. "he was 32 years old" -> 32
    matches = re.findall(r'\b\d+\b', ans_text)

    # 3. check for hedging (ans: "32 or 33") 
    if len(matches) == 1:
        return int(matches[0])
    if len(matches) > hard_cap:
        return None 

    # 5. check if the answer is written out in words using w2n
    if not matches:    
        try:
            return int(w2n.word_to_num(ans_text))
        except (ValueError, TypeError):
            return None

def _check_numeric_answer(player_answer_num: int | None,
                         gold_answer: str) -> BaseEvalResults:
    """
    Evaluates a numeric Free Response question by comparing a preprocessed 
    player integer against the extracted integer of the gold answer.
    
    Notes:
        - Relies on an upstream preprocessor to convert player text into a single `int` or `None`.
        - TODO (Phase 2): Upgrade to `float` and `math.isclose()` instead of `int` to 
          safely handle decimal answers and prevent backend crashes during casting
          for answers such as "platform 9 3/4".
          
    Args:
        player_answer_num (int | None): The parsed numeric value from the player's input.
        gold_answer (str): The raw string of the correct answer (e.g. "150" or "150 points").
        
    Returns:
        BaseEvalResults: A standardized dataclass containing the boolean result 
        and the specific resolution tier.
    """
    result = BaseEvalResults()
    
    # 1. process gold answer
    clean_gold = _normalize_numeric_text(gold_answer)
    gold_matches = re.findall(r'\b\d+\b', clean_gold)
    if not gold_matches:
        # failsafe: Prevent an IndexError if gold_answer contains no digits
        result.is_correct = False
        result.resolution_tier = 'numeric_exact_fail_invalid_gold'
        return result

    correct_answer = int(gold_matches[0])
    
    # 2. if the player answer did not have any numbers
    if player_answer_num is None:
        result.is_correct = False
        result.resolution_tier = 'numeric_exact_fail_invalid_or_no_num'
        return result
    
    # 3. check if the correct number is provided
    if player_answer_num == correct_answer:
        result.is_correct = True
        result.resolution_tier = 'numeric_exact_pass'
        return result
    
    # 4. catch all fail
    result.is_correct = False
    result.resolution_tier = 'numeric_exact_fail'
    return result
    
## 3.2 Date-format answers

def _normalize_date_text(raw_text: str) -> str:
    """
    Shared helper to clean and translate raw chronological strings 
    for both player answers and gold dataset answers.
    """
    text = str(raw_text).lower().strip()
    
    # Strip parenthetical hedges (e.g., "halloween (or october 31st)")
    text = re.sub(r'\(.*?\)', '', text)
    
    # Holiday translation pass
    for holiday, date_str in HOLIDAY_MAP.items():
        if holiday in text:
            text = text.replace(holiday, date_str)
            
    return text

def _preprocess_date_player_ans(raw_player_ans: str, hard_cap:int=1) -> date | None:
    """
    Sanitizes raw player text into a strict date format.
    Includes a translation pass for named holidays
    """
    # 1. normalize answer (strip white space, any 1000 comma separater)
    ans_text = _normalize_date_text(raw_player_ans)
    
    # 2. convert to date text to standardized date
    found_dates = search_dates(ans_text, 
        settings={'STRICT_PARSING': False, 'PREFER_DAY_OF_MONTH': 'first'})
    
    # 3. in case no dates are found:
    if not found_dates:
        return None
    
    # 4. check for hedging
    if len(found_dates)>hard_cap:
        return None
    
    # 5. extract and return single date object 
    # search_dates returns a list of tuples: [('found string', datetime_obj)]
    extracted_datetime = found_dates[0][1]
    return extracted_datetime.date()
            
def _check_date_answer(player_ans_date: date | None, gold_answer: str)->BaseEvalResults:
    """
    Evaluates a date-type player answers by comparing preprocessed 
    player dates against the parsed gold answer date.
    """    
    result = BaseEvalResults()
    
    # 1. process gold answer (convert into standard python datetime)
    clean_gold = _normalize_date_text(gold_answer)
    gold_matches = search_dates(clean_gold, 
        settings={'STRICT_PARSING': False, 'PREFER_DAY_OF_MONTH': 'first'})
    
    if not gold_matches:
        # failsafe: Prevent an IndexError if gold_answer contains no dates
        result.is_correct = False
        result.resolution_tier = 'date_exact_fail_invalid_gold'
        return result
    
    correct_date = gold_matches[0][1].date()
    
    # 2. check if player didn't provide dates
    if player_ans_date is None:
        result.is_correct = False
        result.resolution_tier = 'date_exact_fail_invalid_player_ans'
        return result
    
    # 3. check if the correct date is provided
    if player_ans_date == correct_date:
        result.is_correct = True
        result.resolution_tier = 'date_exact_pass'
        return result
    
    # 4. catch all fail
    result.is_correct = False
    result.resolution_tier = 'date_exact_fail'
    return result

## --- 4. Router for evaluation ---

## 4.1. subrouter for non-text answer evaluation

def _route_nontext_eval(player_answer: str, 
                        gold_answer: str, 
                        answer_type: AnswerType) -> BaseEvalResults:
    """
    Sub-router handling all deterministic, strict-match non-textual answers
    """
    # --- 1. numeric or year answer ---
    if answer_type in [AnswerType.NUMERIC, AnswerType.YEAR]:
        # 1. preprocess the player answer
        processed_player_num = _preprocess_numeric_player_ans(player_answer, hard_cap=1)
        # 2. route to evaluator
        return _check_numeric_answer(processed_player_num, gold_answer)
    
    # --- 2. date answer ---
    elif answer_type == AnswerType.DATE:
        # 1. preprocess the player answer
        processed_player_date = _preprocess_date_player_ans(player_answer, hard_cap=1)
        # 2. route to evaluator
        return _check_date_answer(processed_player_date, gold_answer)
    
    # --- 3. catchall for unknown answer-type ---
    result = BaseEvalResults()
    result.is_correct = False
    result.resolution_tier = 'routing_error_unknown_non_text'
    return result

def _route_text_eval():
    pass

def evaluation_router():
    pass    