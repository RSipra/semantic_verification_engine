"""
Project: SVE (ref implementation: Harry Potter Trivia)
PHASE 2 Tracer -> Context Refinery: NLP Lab (Answer checking logic)
"""
## setup / imports
import time
from datetime import datetime
from typing import List, Tuple, cast
import json
import os
import warnings
from functools import wraps
import pandas as pd
import numpy as np
from sentence_transformers import util
import torch
from rapidfuzz import fuzz
import regex as re
from dateparser.search import search_dates
from word2number import w2n
from pydantic import BaseModel, Field, model_validator, ValidationError
import google.generativeai as genai

from dotenv import load_dotenv, find_dotenv
from core.embeddings import get_sbert_model, sbert_settings, get_nli_model, nli_settings
from core.models import (
    ProductionStandard_Green, ProductionMCQ_Green, 
    ProductionStandard_Blue, ProductionMCQ_Blue, 
    RUNTIME_REGISTRY)
from ds_utils.tracer_descp_features_v0 import count_clean_words
from ds_utils.ds_constants import AnswerType, QuestionType
import ds_utils.tracer_validation_v0 as validation_pipeline

# --configure API for LLM judge for EX evaluator--
load_dotenv(find_dotenv("config.env"), override=True)
google_api_key = os.environ.get('GEMINI_API_KEY')
if not google_api_key:
    raise ValueError("Error: GOOGLE_API_KEY not found.")
genai.configure(api_key=google_api_key)  # type: ignore

## constants and thresholds
HOLIDAY_MAP ={
    "halloween":"october 31",
    "valentines day": "february 14",
    "valentine's day": "february 14",
    "christmas": "december 25",
    "christmas eve": "december 24",
    "new years eve": "december 31",
    "new year's eve": "december 31"
}
# instantiate nli model
nli_model = get_nli_model() 

# LLM models to use for API calls
PRIMARY_MODEL = "models/gemini-3.1-flash-lite-preview"
FALLBACK_MODEL = "models/gemini-flash-latest" 

## Sematnic threshold configuration classes by QuestionType (FR, EX, MCQ)
# NOTE: using Pydantic models instead of dataclass to export live game telemetry

FUZZY_THRESHOLD = 0.85 

class MCQThresholdConfig(BaseModel):
    """
    Semantic thresholds for MCQ (Multiple Choice Question types) evaluation tiers.
    Attributes:
        fuzzy: normalized ratio (0-1) for character similarity (catches 1-2 letter typos), 
        primary SBERT: cutoff for cosine similarity score between player and gold dataset
            answer for a direct pass from SBERT tier.
        distractor_delta: player answer comparison against distractors vs. correct answer
    """
    fuzzy_threshold: float = FUZZY_THRESHOLD
    semantic_threshold: float = 0.75
    distractor_delta: float = 0.30

class FRThresholdConfig(BaseModel):
    """
    Semantic thresholds for FR (Factual Recall type questions) evaluation tiers.
    Attributes:
        fuzzy: normalized ratio (0-1) for character similarity (catches 1-2 letter typos),
        primary SBERT: cutoff for cosine similarity score between player and gold dataset
            answer for a direct pass from SBERT tier. Also ceiling for ambiguous score region.
        ambiguous_answer_floor: lower threshold for ambiguous similarity scores. Scores below
            threshold fail SBERT tier.
        entity_ref_match_boost: boost to apply if player answer contains a known entity reference / alias.
        fr_ans_len_outlier_wc: word count cutoff for FR long answers, based on Legacy data FR answer length
            distributon (Q3 + 1.5*IQR) = 6.
    """
    fuzzy_threshold: float = FUZZY_THRESHOLD
    semantic_threshold: float = 0.80
    ambiguous_answer_floor: float = 0.50
    entity_ref_match_boost: float = 0.10
    fr_ans_len_outlier_wc: int = 6

class EXThresholdConfig(BaseModel):
    """
    Semantic thresholds for EX (Explanatory type questions) evaluation tiers.
    Attributes:
        fuzzy: normalized ratio (0-1) for character similarity (catches 1-2 letter typos), 
        primary SBERT: cutoff for cosine similarity score between player and gold dataset 
            answer for a direct pass from SBERT tier. Also ceiling for ambiguous score region.
    """
    fuzzy_threshold: float = 0.95
    semantic_threshold: float = 0.80
    ambiguous_answer_floor: float = 0.40

## Structured output: Answer Evaluation Results 
# standardizing answer evaluation metrics into data classes

class BaseEvalResults(BaseModel):
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
    
    @model_validator(mode='after')
    def round_all_floats(self) -> 'BaseEvalResults':
        """
        Automatically rounds all float fields in this class and any 
        subclass to 4 decimal places.
        """
        PRECISION = 4  
        
        # self.__dict__ holds successfully validated data
        for field_name, value in self.__dict__.items():
            if isinstance(value, float):
                setattr(self, field_name, round(value, PRECISION))
                
        # Pydantic v2: 'after' validator must return the modified instance
        return self

## MCQ 

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
    execution_time_sec: float = 0.0

## FR
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
    llm_model_used: str | None = None
    llm_mc_response: str = ""
    llm_reasoning: str = ""
    execution_time_sec: float = 0.0

## EX
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
    llm_model_used: str | None = None
    llm_mc_response: str = ""
    llm_reasoning: str = ""
    execution_time_sec: float = 0.0 

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
    Hydrates a raw dictionary into a strictly-typed Pydantic object.
    Uses 'model_construct' for speed if you've already validated 
    upstream in the publishing pipeline.
    """
    # 1. Identify the question type for row
    dict_q_type = row_dict.get('question_type')
    if dict_q_type is None:
        raise ValueError((f"CRITICAL: Row missing 'answer_type'. \
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
    
    # 4. validate using pydantic mdoel field validator (tensor shapes)
    try:
        return pydantic_model_class.model_validate(row_dict)
        
    except ValidationError as e:
        m_id = row_dict.get('master_id', 'UNKNOWN_ID')
        print(f"🚨 [Data Integrity Error] Question ID: {m_id}")
        print(f"Reason: {e}")
        
        # Re-raise so the session start fails safely
        raise 
    
    # 5. create and return the Question object based on question type with row data
    return pydantic_model_class.model_validate(row_dict)

## LLM calls helpers and method

# utilties to save llm run evaluation logs as json dumps
def save_cache(log_filepath: str, log_dict: dict):
    """Saves evaluation logs to a local JSON file."""
    with open(log_filepath,"w") as f:
        json.dump(log_dict, f)
        print("Test executed and results cached.")
        
def load_cache(cache_filepath: str)-> dict:
    """ """
    if os.path.exists(cache_filepath):
        with open(cache_filepath, "r") as f:
            log_data = json.load(f)
        print("Loaded {cache_filepath.name} from local cache.")
        return log_data
    else:
        print("WARNING: No cache found. You must set run_test=True at least once.")
        return {}  # failsafe empty state 

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

# system prompt for FR (Factual Recall) LLM judge
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
    # ordered to push model to think before assigning boolean
    reasoning: str = Field(description="Step-by-step logical proof of why the answer fails or passes the strict criteria.")
    mc_dialogue: str = Field(description="A short, 1-sentence in-character reaction from the quiz host.")
    # The boolean comes LAST, after the logic is established
    is_correct: bool = Field(description="True ONLY if the reasoning proves absolute semantic and entity alignment.")

# warmup function to mitigate cold start latency for the first few LLM calls in the evaluation loop
def warmup_llm_connection(model_name: str = PRIMARY_MODEL, 
                          system_prompt: str = SYSTEM_PROMPT_EX):
    """
    Standalone network ping to absorb the 6-second gRPC cold-start penalty.
    Run this once before the main evaluation loop.
    """
    print(f"--- Initiating LLM Network Handshake ---")
    print(f"Target: {model_name}")
    start_time = time.time()
    
    try:
        # 1. Initialize the model using your exact genai syntax 
        #    System instructions for EX (most LLM calls) added upfront to avoid cold start penalty
        #    on the first real evaluation call.
        ping_model = genai.GenerativeModel(model_name=model_name,  # type: ignore
                                           system_instruction=system_prompt)  
        
        # 2. Send the smallest possible payload to open the connection and 
        #    compile the response schema (LLMJudgeResponse) to mitigate the 
        #    cold start penalty for future calls.
        _ = ping_model.generate_content(
            "Return a dummy response",
            generation_config=genai.GenerationConfig(  # type: ignore
                response_mime_type="application/json",
                response_schema=LLMJudgeResponse, 
            )
        )
        
        end_time = time.time()
        print(f"✅ Connection established. Warmup time: {round(end_time - start_time, 2)} seconds.")
        print("The network pipe is now open for _call_llm_judge.\n")
        
    except Exception as e:
        print(f"⚠️ Warmup failed. The first call to _call_llm_judge will carry the cold-start penalty.")
        print(f"Error Details: {str(e)}\n")

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
                    system_prompt: str,
                    delay_seconds: float = 6.0) -> tuple[LLMJudgeResponse, str]:
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
                request_options={"timeout": 60.0}
            )
            end_time = time.time()
            print(f"LLM resolution time: {round(end_time - start_time, 2)} seconds")
            # 2. conservative rate Limiting (10 RPM / 6s buffer)
            time.sleep(delay_seconds)
            
            # clean markdown formatting before parsing
            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            elif raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            
            # 3. validation
            payload = LLMJudgeResponse.model_validate_json(raw_text.strip())    
            return payload, target_model

        except Exception as e:
            print(f"\n⚠️ API CRASH/TIMEOUT for Question: {question}")
            print(f"Error Details: {str(e)}\n")
            error_msg = str(e).lower()
            
            # Catch Rate Limits (429), Timeouts (deadline), and Server Errors (503/500)
            if any(code in error_msg for code in ["429", "404", "503", "500", "deadline", "timeout"]):
                print(f"⚠️ {target_model} failed or timed out... Attempting fallback.")
                time.sleep(10.0)
                continue # <-- pushes it to  FALLBACK_MODEL
            time.sleep(4.0) # sleep even on errors to cool down the connection
            error_payload = LLMJudgeResponse(
                is_correct=False,
                mc_dialogue="The Restricted Section is currently off-limits.",
                reasoning=f"System error: {str(e)}")
            return error_payload, target_model
            
    # 4. Graceful Degradation if entire cascade fails
    fail_payload = LLMJudgeResponse(is_correct=False,
                                    mc_dialogue="The Floo Network is currently congested.",
                                    reasoning="System error: All LLM tiers failed or exceeded quota.")
    return fail_payload, "cascade_failed"

## --- 1. DATASET PREPROCESSING ---
## Add tensors for embedding columns

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

## 2. --- Evaluator Testing ----
def flatten_test_suite(nested_suite: dict) -> list[dict]:
    """
    Converts a nested, human-readable test suite dictionary into a flat list
    of test cases compatible with the universal test harness.
    
    Args:
        nested_suite (dict): A dictionary grouped by q_id containing 'test_cases'.
        
    Returns:
        list[dict]: A flattened list where each dict is a single test execution.
    """
    flat_cases = []
    
    for q_id, q_data in nested_suite.items():
        # Safety check: skip if the question doesn't have a test_cases array
        if 'test_cases' not in q_data:
            continue
            
        for idx, case in enumerate(q_data['test_cases'], 1):
            flat_case = {
                'q_id': q_id,
                # Map the nested 'player_answer' key to the 'answer' key the harness expects
                'answer': case.get('player_answer', ''),  
                'expected': case.get('expected', ''),
                'test_type': case.get('test_type', 'unknown') # Keep for your own records
            }
            flat_cases.append(flat_case)
            
    return flat_cases

## 2.1 Run Evaluator tests
def run_evaluator_test_suite(test_cases: list[dict], 
                             runtime_df: pd.DataFrame,
                             enable_llm_escalation: bool = False,
                             enable_nli_escalation: bool = False,
                             treat_fr_as_ex: bool = False) -> dict:
    """
    A universal testing harness for the Semantic Verification Engine.
    Dynamically routes test cases to the correct MCQ, FR, or EX evaluator,
    tracks execution latency, measures LLM escalation rates, and returns detailed logs.
    """
    print(f"🚀 Starting Universal Evaluation Suite\n" + "-"*50)
    print(f"   LLM Escalation (FR, EX only): {'ON' if enable_llm_escalation else 'OFF'}")
    print(f"   NLI Escalation (EX only): {'ON' if enable_nli_escalation else 'OFF'}")
    if treat_fr_as_ex:
        print(f"   ⚠️ OVERRIDE ACTIVE: Routing FR questions through EX evaluator")
    print("-" * 50)
    
    total_cases = len(test_cases)
    pass_count = 0
    llm_escalation_count = 0
    llm_pass_count = 0
    
    total_execution_time = 0.0
    total_local_time = 0.0
    total_llm_time = 0.0
    
    evaluation_logs = {"passed": [], "failed": []}

    for i, test in enumerate(test_cases, 1):
        # 1. Safely extract test case data
        q_id = test['q_id']
        test_id = i
        player_answer = test['answer'].lower().strip()
        
        # smart boolean conversion
        expected_raw = test['expected']
        expected_bool = (expected_raw is True or str(expected_raw).lower() == 'correct')
        
        print(f"  -> [Case {test_id}]. Testing: '{player_answer}'")
            
        # 2. Hydrate the Question Object
        q_data = get_question_dict(runtime_df, q_id)
        q = question_factory(q_data)
        
        # Determine question type for logging (MCQ models might not have a question_type string)
        q_type_str = getattr(q, 'question_type', 'MCQ')
        
        # 3. THE ROUTER LOGIC: Dynamically dispatch to the correct evaluator
        if isinstance(q, (ProductionMCQ_Green, ProductionMCQ_Blue)):
            # MCQ does not utilize LLM or NLI escalation
            result = check_mcq_answer(player_answer, q)

        elif isinstance(q, (ProductionStandard_Green, ProductionStandard_Blue)):
            if q.question_type == 'FR' and not treat_fr_as_ex:
                result = check_fr_answer(player_answer, q, 
                                         enable_llm_escalation=enable_llm_escalation)
            elif q.question_type == 'EX' or (q.question_type == 'FR' and treat_fr_as_ex):
                result = check_ex_answer(player_answer, q, 
                    enable_llm_escalation=enable_llm_escalation,
                    enable_nli_escalation=enable_nli_escalation)
            else:
                raise ValueError(f"Standard Question {q_id} has unrecognized type: {q.question_type}")
        else:
            raise TypeError(f"Unknown Pydantic model for QID {q_id}")
        
        # 4. Process Results & Telemetry
        outcome = result.is_correct
        test_passed = (outcome == expected_bool)
        status = "✅ PASS" if test_passed else "❌ FAIL"
        
        # Safely extract execution time injected by your @track_eval_latency decorator
        case_time = float(result.execution_time_sec) if getattr(result, 'execution_time_sec', None) else 0.0
        total_execution_time += case_time
        
        # Route latency metrics based on resolution tier
        if result.resolution_tier and "llm_judge" in result.resolution_tier:
            total_llm_time += case_time
            llm_escalation_count += 1
            if test_passed:
                llm_pass_count += 1
        else:
            total_local_time += case_time
        
        # Build the log entry
        log_entry = {
            'test_id': test_id,
            'q_id': q_id,
            'q_type': q_type_str,
            'player_answer': player_answer,
            'expected': expected_bool,
            'got': outcome,
            'telemetry': result
        }
        
        if test_passed:
            pass_count += 1
            evaluation_logs["passed"].append(log_entry)
        else:
            evaluation_logs["failed"].append(log_entry)
            
        # 5. Print Individual Test Output
        print(f"{i}. {status}: QID {q_id} [{q_type_str}] | Expected: {expected_bool} | Got: {outcome}")
        print(f"   Tier: {result.resolution_tier} | Time: {case_time:.4f}s")
        
        # Exclude fields we already printed or that are too massive for a 1-liner
        excluded_fields = {'is_correct', 'resolution_tier', 'execution_time_sec', 'llm_mc_response', 'llm_reasoning'}
        telem_dict = result.model_dump(exclude=excluded_fields)
        
        # Format into a clean key=value string, ignoring None values
        telem_str = ", ".join([f"{k}={v}" for k, v in telem_dict.items() if v is not None])
        print(f"   Metrics: {telem_str}")
        
        llm_reasoning_text = getattr(result, 'llm_reasoning', None)
        # If it hit the LLM, print the reasoning on a new line so you can read the logic
        if "llm_judge" in result.resolution_tier and llm_reasoning_text:
            print(f"   LLM Reasoning: {llm_reasoning_text}")
            
        print() # blank line for visual spacing between test cases
        
    # 6. Generate Summary
    pass_percentage = (pass_count / total_cases) * 100 if total_cases > 0 else 0
    llm_percentage = (llm_escalation_count / total_cases) * 100 if total_cases > 0 else 0
    llm_accuracy = (llm_pass_count / llm_escalation_count) * 100 if llm_escalation_count > 0 else 0
    
    # Calculate Latency Averages
    avg_total_time = total_execution_time / total_cases if total_cases > 0 else 0
    local_cases = total_cases - llm_escalation_count
    avg_local_time = total_local_time / local_cases if local_cases > 0 else 0
    avg_llm_time = total_llm_time / llm_escalation_count if llm_escalation_count > 0 else 0

    print("="*50)
    print("📊 UNIVERSAL TEST SUITE SUMMARY")
    print("="*50)
    print(f"Total test cases:     {total_cases}")
    print(f"Cases that passed:    {pass_count} ({pass_percentage:.2f}%)")
    print(f"Cases that failed:    {total_cases - pass_count} ({100 - pass_percentage:.2f}%)")
    print("-" * 50)
    print(f"Avg Overall Latency:  {avg_total_time:.4f}s")
    print(f"Avg Local Latency:    {avg_local_time * 1000:.2f}ms (SBERT/NLI path)")
    print(f"Avg LLM Latency:      {avg_llm_time:.2f}s (Escalation path)")
    print("-" * 50)
    print(f"LLM Escalations:      {llm_escalation_count} ({llm_percentage:.2f}% of total traffic)")  
    if llm_escalation_count > 0:
        print(f"LLM Test Accuracy:    {llm_pass_count}/{llm_escalation_count} ({llm_accuracy:.2f}%)") 
    
    return evaluation_logs

### --- 3. TEXT ANSWER EVALUATORS ---
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

### 3.1 MCQ (multiple choice)
# MCQ with a 'text' answer type (can be evaluated with fuzzy matching and semantic similarity)
@track_eval_latency
def check_mcq_answer(player_answer:str,
                     q: ProductionMCQ_Green | ProductionMCQ_Blue,
                     config: MCQThresholdConfig = MCQThresholdConfig()
                     ) -> MCQEvalResults:
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
    1. Input Normalization: This function expects `player_answer` to be pre-normalized 
       (lowercased, stripped of trailing whitespace). Do not pass raw user input directly 
       to this method. Use the `_preprocess_text_player_ans()` upstream helper first.  
    2. Tensor Hydration: This function assumes the system has completed the session 
       warmup phase. The `q` object must have its optional PyTorch tensor matrices 
       (gold answer, variations, and distractors) fully instantiated before evaluation.  

    Args:
        player_answer (str): The normalized text input submitted by the player.
        q (ProductionMCQ_Green): The strictly-typed Question object containing the gold 
            answer and hydrated tensor matrices.
        config (MCQThresholdConfig, optional): The threshold settings for this evaluator. 
            Defaults to standard MCQ thresholds.

    Returns:
        MCQEvalResults: A strictly typed payload containing the verification results 
            and nested telemetry.
    """
    # unpack necessary attributes from the `q` Question object
    gold_answer = q.answer
    gold_ans_tensor = q.answer_embeddings_tensor
    answer_variation_tensor_matrix = q.answer_variations_embeddings_tensor_matrix
    distractor_tensor_matrix = q.mcq_distractors_embeddings_tensor_matrix
    
    # --Type checker & Tensor hydration--
    # -> since tensors are Optional in `q` because they are calculated at game warmup
    # but need to be available in game.
    # These assertions narrow the type from (Tensor | None) -> Tensor
    assert gold_ans_tensor is not None, \
        f"CRITICAL: Missing answer tensor for Question [{q.master_id}]. Was hydration skipped?"
    assert answer_variation_tensor_matrix is not None, \
        f"CRITICAL: Missing variations matrix for Question [{q.master_id}]."
    assert distractor_tensor_matrix is not None, \
        f"CRITICAL: Missing distractor matrix for Question [{q.master_id}]."
    # confirm preprocessing in place
    assert player_answer == player_answer.lower(), \
        "CRITICAL: player_answer must be lowercased before reaching the MCQ checker." 
    # normalization of player ans is handled upstream of question_type specific helper
    
    # initialize mcq results instance
    result = MCQEvalResults()
    
    # TIER 1: fast path (exact match) --> use case: perfect answers 
    if _is_exact_match(player_answer, gold_answer):
        # update and return results 
        result.is_correct = True
        result.resolution_tier = 'mcq_exact'
        result.fuzzy_score = 1.00
        return result
    
    # TIER 2: intermediate path (fuzzy match -> use case: typos, spelling mistakes in short ans (FR, MCQ)
    result.fuzzy_score = round(_is_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= config.fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "mcq_fuzzy"
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
    distractor_scores = (util.cos_sim(player_tensor, distractor_tensor_matrix)[0])
    max_dist_score = torch.max(distractor_scores).item()
    
    margin = correct_ans_score - max_dist_score
    
    # 3. update results telemetry metrics
    result.sim_correct_ans = round(correct_ans_score,4)
    result.sim_distractor = round(max_dist_score,4)
    result.margin =  round(margin, 4)
    result.matched_variation =  matched_variation # True if a variation (likely shorthand used)
    
    if correct_ans_score >= config.semantic_threshold and margin >= config.distractor_delta:
        result.is_correct= True
        result.resolution_tier=  "mcq_passed_semantic"
    else:
        result.is_correct = False
        result.resolution_tier = "mcq_failed_semantic"
    
    return result

### 3.2 FR (Factual Recall)

@track_eval_latency
def check_fr_answer(player_answer: str,
                    q: ProductionStandard_Green | ProductionStandard_Blue,
                    config: FRThresholdConfig = FRThresholdConfig(),
                    enable_llm_escalation: bool = False  #for notebook experiments only
                    ) -> FREvalResults:
    """
    Evaluates a player's Factual Recall (open-text) answer using a 4-Tier logic.
    
    Because FR lacks the safety net of MCQ distractors, this function utilizes a stricter 
    baseline semantic threshold combined with an *entity boost*. It mathematically 
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
      
    WARNING: Contractual Assumptions
    1. Input Normalization: This function expects `player_answer` and all strings within 
       `entity_refs` to be pre-normalized (lowercased, stripped of trailing whitespace). 
       Do not pass raw user input directly to this method. Use the upstream helper first.  
    2. Tensor Hydration: This function assumes the system has completed the session 
       warmup phase. The `q` object must have its PyTorch tensor matrices fully instantiated.  

    Args:
        player_answer (str): The normalized text input submitted by the player.
        q (ProductionStandard_Green | ProductionStandard_Blue): The strictly-typed Question 
            object containing the gold answer, entity refs, and hydrated tensor matrices.
        config (FRThresholdConfig, optional): The threshold control board for this evaluator. 
            Defaults to standard FR thresholds.
        enable_llm_escalation (bool, optional): Allows routing to the LLM judge for length 
            outliers. Defaults to False.

    Returns:
        FREvalResults: A strictly typed payload containing the verification results 
            and nested telemetry.
    """
    # unpack necessary attributes from the `q` Question object
    question = q.question
    gold_answer = q.answer
    gold_answer_word_count = q.answer_length
    answer_variations = q.answer_variations
    source_quote = q.source_quote or ""  # not available for legacy questions
    explanation = q.explanation
    entity_refs = q.semantic_entity_refs
    
    # Type checker & tensor hydration -- confirm preprocessing in place
    assert q.answer_embeddings_tensor is not None, \
        f"CRITICAL: Missing answer tensor for Question [{q.master_id}]. Was hydration skipped?"
    assert q.answer_variations_embeddings_tensor_matrix is not None, \
        f"CRITICAL: Missing variations matrix for Question [{q.master_id}]."
    assert player_answer == player_answer.lower(), "CRITICAL: player_answer must be lowercased before reaching the FR checker." 
    
    gold_ans_tensor=q.answer_embeddings_tensor
    answer_variation_tensor_matrix= q.answer_variations_embeddings_tensor_matrix
    
    # initialize FR metrics results object
    result = FREvalResults()
    
    # TIER 1: fast path (exact match) --> use case: perfect answers
    if _is_exact_match(player_answer, gold_answer):
        result.is_correct = True
        result.resolution_tier = 'fr_exact'
        result.fuzzy_score = 1.00
        return result

    # TIER 2: intermediate path (fuzzy match -> use case: typos, spelling mistakes in short ans (FR, MCQ)
    result.fuzzy_score = round(_is_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= config.fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "fr_fuzzy"
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
    is_outlier = player_ans_wc > config.fr_ans_len_outlier_wc   # exceeds legacy outlier ans word count
    # verbose player ans: if twice the len of expected and wc in vector dilution range of sbert
    is_disproportionate = (player_ans_wc >= 2 * gold_answer_word_count) and (player_ans_wc >= 8) 
        
    if enable_llm_escalation and (is_outlier or is_disproportionate):
        llm_judgment, executing_model = _call_llm_judge(question,
                                                        gold_answer, 
                                                        player_answer,
                                                        answer_variations,
                                                        source_quote,
                                                        explanation,
                                                        SYSTEM_PROMPT_FR_SPECIALIST)
    
        if llm_judgment.is_correct:
            result.is_correct = True
            result.resolution_tier = 'fr_llm_judge_pass'
        else:
            result.is_correct = False
            result.resolution_tier = 'fr_llm_judge_fail'
        # update llm metrics
        result.llm_model_used = executing_model     
        result.llm_mc_response = llm_judgment.mc_dialogue
        result.llm_reasoning = llm_judgment.reasoning
        return result
            
    # Path B: player answer meets threshold immediatetly
    elif correct_ans_score >= config.semantic_threshold:
        result.is_correct = True
        result.resolution_tier = 'fr_passed_primary_semantic'
        return result

    # Path C: ambiguous range (boost score if any term matches entity_refs)
    elif correct_ans_score < config.semantic_threshold and correct_ans_score >= config.ambiguous_answer_floor:
        
        # Initialize (prevent UnboundLocalError)
        matched_term = None
        boost_applied = 0.0
        updated_correct_ans_score = correct_ans_score
        
        for entity in entity_refs:
            # use regex with word boundaries matching entity
            pattern = r'\b' + re.escape(entity.lower()) + r'\b'
            if re.search(pattern, player_answer):
                matched_term = entity
                boost_applied = config.entity_ref_match_boost
                updated_correct_ans_score = min(1.00, correct_ans_score + boost_applied) 
                break
            # check updated score against treshold again
        if updated_correct_ans_score >= config.semantic_threshold :
            result.is_correct = True
            result.resolution_tier = 'fr_passed_semantic_boosted'
        else:
            result.is_correct = False
            result.resolution_tier = 'fr_failed_semantic_boosted'
        
        # update common telemetry
        result.boost_applied = boost_applied
        result.matched_entity_ref = matched_term
        result.final_boosted_score = round(updated_correct_ans_score,4)
        return result
    
    # Path D: wrong answer (score below the ambiguous threshold)
    else:
        result.is_correct = False
        result.resolution_tier = "fr_failed_primary_semantic"
        return result

### 3.3 EX (Explanatory) 

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
def check_ex_answer(player_answer: str,
                    q: ProductionStandard_Green | ProductionStandard_Blue,
                    config: EXThresholdConfig = EXThresholdConfig(),
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

    The 4 Tiers of Evaluation:
    --------------------------
    - Tier 1/2: O(1) Exact and Fuzzy string matching.
    - Tier 3.1: SBERT vector similarity (filters vocabulary mismatches, features Verbosity Bypass).
    - Tier 3.2: NLI Cross-Encoder (gates inverted logic and contradictions).
    - Tier 4: LLM Judge escalation for the ambiguous region (vague abstractions/deep lore).
    
    WARNING: Contractual Assumptions
    1. Input Normalization: This function expects `player_answer` to be pre-normalized 
       (lowercased, stripped of trailing whitespace). Do not pass raw user input directly. 
    2. Tensor Hydration: This function assumes the system has completed the session warmup 
       phase. The `q` object must have its PyTorch tensor matrices fully instantiated.

    Args:
        player_answer (str): The normalized text input provided by the user.
        q (ProductionStandard_Green | ProductionStandard_Blue): The strictly-typed Question 
            object containing the gold answer, legacy UI data, and hydrated tensor matrices.
        config (EXThresholdConfig, optional): The threshold control board for this evaluator. 
            Defaults to standard EX thresholds.
        enable_llm_escalation (bool, optional): Toggle to activate/deactivate the Tier 4 
            LLM judge for A/B testing. Defaults to True.
        enable_nli_escalation (bool, optional): Toggle to activate/deactivate the Tier 3.2 
            NLI logic gate. Defaults to False.

    Returns:
        EXEvalResults: A populated telemetry object containing the final boolean judgment 
            (`is_correct`), the exact pipeline exit node (`resolution_tier`), and internal NLP scores.
    """
    # unpack necessary attributes from the `q` Question object
    question = q.question
    gold_answer = q.answer
    gold_answer_wordcount = q.answer_length
    answer_variations = q.answer_variations
    source_quote = q.source_quote or ""
    explanation = q.explanation
    
     # Type checker & tensor hydration -- confirm preprocessing in place
    assert q.answer_embeddings_tensor is not None, \
        f"CRITICAL: Missing answer tensor for Question [{q.master_id}]. Was hydration skipped?"
    assert q.answer_variations_embeddings_tensor_matrix is not None, \
        f"CRITICAL: Missing variations matrix for Question [{q.master_id}]."
    assert player_answer == player_answer.lower(),\
        "CRITICAL: player_answer must be lowercased before reaching the EX checker." 
    
    gold_ans_tensor = q.answer_embeddings_tensor
    answer_variation_tensor_matrix = q.answer_variations_embeddings_tensor_matrix
    
    # initialize EX metrics results object
    result = EXEvalResults()
    
    # TIER -1: exact match, grab any O(1) wins
    if _is_exact_match(player_answer, gold_answer):
        result.is_correct = True
        result.resolution_tier = 'ex_exact'
        result.fuzzy_score = 1.00
        return result
    # TIER-2: fuzzy match, grab any O(1) wins
    result.fuzzy_score = round(_is_fuzzy_match(player_answer, gold_answer),4)
    if result.fuzzy_score >= config.fuzzy_threshold:
        result.is_correct = True
        result.resolution_tier = "ex_fuzzy"
        return result

    # TIER-3: semantic resolution (SBERT + NLI)
    player_tensor = _encode_player_answer(player_answer)
    # check similarity of player answer to gold answer, answer variations
    correct_ans_score, matched_variation = _check_semantic_variations(player_tensor,
                                                                      gold_ans_tensor,
                                                                      answer_variation_tensor_matrix)
    # preload base telemetry 
    result.primary_similarity_score = round(correct_ans_score,4)
    result.matched_ans_variation = matched_variation
    
    player_answer_wordcount = count_clean_words(player_answer)
    len_ratio = player_answer_wordcount / max(1, gold_answer_wordcount)

    # Tier 3.1: primary semantic check
    # verbosity bypass to the LLM
    if correct_ans_score < config.ambiguous_answer_floor:
        if len_ratio >= 2.0 and enable_llm_escalation:
            llm_judgment, executing_model = _call_llm_judge(question, 
                                                            gold_answer, 
                                                            player_answer,
                                                            answer_variations,
                                                            source_quote, 
                                                            explanation,
                                                            SYSTEM_PROMPT_EX)
            if llm_judgment.is_correct:
                result.is_correct = True
                result.resolution_tier = 'ex_llm_judge_long_ans_pass'           
            else:
                result.is_correct = False
                result.resolution_tier = 'ex_llm_judge_long_ans_fail'
            # return llm metrics for both cases
            result.llm_model_used=executing_model
            result.llm_mc_response = llm_judgment.mc_dialogue
            result.llm_reasoning = llm_judgment.reasoning
            return result
        else:
            result.is_correct = False
            result.resolution_tier = 'ex_primary_semantic_fail'
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
        result.nli_confidence = round(nli_confidence,4)

        # contradiction fail fast
        if nli_label == 'contradiction':
            result.is_correct = False
            result.resolution_tier = 'ex_nli_contradiction_fail'
            return result

        # entailment pass (high vocab, high directional logic)
        if nli_label == 'entailment' and result.primary_similarity_score >= config.semantic_threshold:
            result.is_correct = True
            result.resolution_tier = 'ex_nli_entailment_pass'
            return result

    # Tier 4: LLM resolution for remaining cases
    #         all 'neutral' AND 'entailment' with ambiguous sbert scores 
    #         (i.e. semantic_threshold < sbert_score <= ambiguous_cutoff)
    
    # notebook experiment LLM bypass: If toggle is off, fail ambiguous answers locally
    if not enable_llm_escalation:
        result.is_correct = False
        result.resolution_tier = 'ex_ambiguous_fail_without_LLM'
        return result
    
    llm_judgment, executing_model = _call_llm_judge(question, 
                                                    gold_answer, 
                                                    player_answer,
                                                    answer_variations, 
                                                    source_quote, 
                                                    explanation,
                                                    SYSTEM_PROMPT_EX)
    
    if llm_judgment.is_correct:
        result.is_correct = True
        result.resolution_tier = 'ex_llm_judge_pass'
    else:
        result.is_correct = False
        result.resolution_tier = 'ex_llm_judge_fail' 
    # update llm metrics
    result.llm_model_used = executing_model
    result.llm_mc_response = llm_judgment.mc_dialogue
    result.llm_reasoning = llm_judgment.reasoning          
    return result

## --- 4. NON-TEXT ANSWERS ---

## 4.1 Numeric answers (number, year)

def _check_for_bc_indicator(answer:str):
    """Check if answer explicitly indicates BC/BCE date."""
    pattern = r'\b(bc|bce|b\.c\.|b\.c\.e\.)\b'
    return bool(re.search(pattern, answer.lower()))

def _normalize_numeric_text(raw_answer:str):
    """
    Shared helper to clean and translate numeric or year strings 
    for both player answers and gold dataset answers.
    """
    # 1. base string cleanup
    clean_text = str(raw_answer).lower().strip().replace(",", "")
    
    # 2. clamp floating minus signs (turns "- 1718" into "-1718")
    clean_text = re.sub(r'-\s+', '-', clean_text)
    
    return clean_text

def _preprocess_numeric_player_ans(raw_player_ans:str,
                                   answer_type:str, 
                                   hard_cap:int = 1):
    """
    Sanitizes raw player text into a single integer.
    Enforces an anti-hedging hard cap of 1.
    Returns None if hedging is detected or no valid number is found.
    """
    # 1. normalize answer (strip white space, any 1000 comma separater)
    ans_text = _normalize_numeric_text(raw_player_ans)
    
    # 2. check if year has BC or BCE,
    # check if gold answer has BC or BCE:
    is_bc = False
    if answer_type=='year':
        is_bc = _check_for_bc_indicator(ans_text)
        
    # 2. extract numbers from surrounding text -> e.g. "he was 32 years old" -> 32
    matches = re.findall(r'(?<!\w)-?\b\d+\b', ans_text)
    
    # 3. check for hedging (ans: "32 or 33") and if BC if the answer is year 
    if len(matches) == 1:
        # if the year is BC or BCE:
        num = int(matches[0])
        # add indicator that it is BC year by making negative
        return -1 * abs(num) if is_bc else num

    if len(matches) > hard_cap:
        return None 

    # 5. check if the answer is written out in words using w2n
    if not matches:    
        try:
            num = int(w2n.word_to_num(ans_text))
            # check if bc year check applies 
            return num * -1 if is_bc else num
        except (ValueError, TypeError):
            return None

def _check_numeric_answer(player_answer_num: int | None,
                          answer_type: AnswerType,
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
    correct_answer = _preprocess_numeric_player_ans(gold_answer, answer_type=answer_type)
    
    if correct_answer is None:
        # failsafe: Prevent an IndexError if gold_answer contains no digits
        result.is_correct = False
        result.resolution_tier = 'numeric_exact_fail_invalid_gold'
        return result
    
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
    
## 4.2 Date-format answers

def _normalize_date_text(raw_text: str) -> str:
    """
    Shared helper to clean and translate raw chronological strings 
    for both player answers and gold dataset answers.
    """
    text = str(raw_text).lower().strip()
    
    # Strip parenthetical hedges (e.g., "halloween (or october 31st)")
    text = re.sub(r'\(.*?\)', '', text)
    # Strips ordinals (st, nd, rd, th, rst) that are attached to numbers
    # Turns "31rst" -> "31", "22nd" -> "22"
    text = re.sub(r'(?<=\d)(st|nd|rd|th|rst)\b', '', text)
    
    # Holiday translation pass
    for holiday, date_str in HOLIDAY_MAP.items():
        if holiday in text:
            text = text.replace(holiday, date_str)
            
    return text

def _extract_date_entities(date_string: str) -> dict | None:
    """
    Parses a raw string into Day, Month, and Year entities.
    Accurately detects missing years and assigns them None.
    Returns None if the string isn't a valid date.
    AI written (Gemini)
    """
    # 1. Clean the text (Assumes you added the ordinal regex patch from earlier)
    clean_text = _normalize_date_text(date_string)
    
    base_1 = datetime(1900, 1, 1)
    base_2 = datetime(2000, 12, 31)
    
    # 2. Use search_dates to pluck the date out of conversational fluff
    search_1 = search_dates(clean_text, settings={'RELATIVE_BASE': base_1, 'PREFER_DAY_OF_MONTH': 'first'})
    search_2 = search_dates(clean_text, settings={'RELATIVE_BASE': base_2, 'PREFER_DAY_OF_MONTH': 'first'})
    
    # Failsafe: If no dates are found in the text at all
    if not search_1 or not search_2:
        return None
        
    # 3. Extract the first date found in the string
    parse_1 = search_1[0][1]
    parse_2 = search_2[0][1]
    matched_text = search_1[0][0] # The exact substring the parser thinks is a date
    
    # 4. System Year Hallucination Failsafe
    is_hallucinated_year = parse_1.year != parse_2.year
    current_year = datetime.now().year
    
    if parse_1.year == current_year and not is_hallucinated_year:
        year_str = str(current_year)
        short_year = year_str[-2:]
        
        # Did they actually type '2026' or '26' in the matched substring?
        if year_str not in matched_text:
            short_year_count = matched_text.count(short_year)
            day_matches_short = (parse_1.day == int(short_year))
            if short_year_count <= (1 if day_matches_short else 0):
                is_hallucinated_year = True

    # 5. Build and return the hallucination-proof dictionary
    entities: dict[str, int | None] = {
        'day': parse_1.day if parse_1.day == parse_2.day else None,
        'month': parse_1.month if parse_1.month == parse_2.month else None,
        'year': None if is_hallucinated_year else parse_1.year
    }
    
    return entities
            
def _check_date_answer(player_entities: dict[str, int | None] | None, gold_answer: str)->BaseEvalResults:
    """
    Evaluates a date-type player answers by comparing preprocessed 
    player dates against the parsed gold answer date.
    """    
    result = BaseEvalResults()
    
    # 1. process gold answer (convert into standard python datetime)
    clean_gold = _normalize_date_text(gold_answer)
    gold_entities = _extract_date_entities(clean_gold)
    
    if not gold_entities:
        # failsafe: Prevent an IndexError if gold_answer contains no dates
        result.is_correct = False
        result.resolution_tier = 'date_exact_fail_invalid_gold'
        return result
    
    # 2. check if player didn't provide dates
    if player_entities is None:
        result.is_correct = False
        result.resolution_tier = 'date_exact_fail_invalid_player_ans'
        return result
    
    # 3. check if the correct date is provided
    if player_entities == gold_entities:
        result.is_correct = True
        result.resolution_tier = 'date_exact_pass'
        return result
    
    # 4. catch all fail
    result.is_correct = False
    result.resolution_tier = 'date_exact_fail'
    return result

## --- 5. Router for evaluation ---

## 5.1. subrouter for non-text answer evaluation

def _route_nontext_eval(player_answer: str, 
                        q: ProductionStandard_Green | 
                           ProductionStandard_Blue  |
                           ProductionMCQ_Green      |
                           ProductionMCQ_Blue) -> BaseEvalResults:
    """
    Sub-router handling all deterministic, strict-match non-textual answers
    """
    # --- 1. numeric or year answer ---
    if q.answer_type in [AnswerType.NUMERIC, AnswerType.YEAR]:
        # 1. preprocess the player answer
        processed_player_num = _preprocess_numeric_player_ans(player_answer, q.answer_type, hard_cap=1)
        # 2. route to evaluator
        return _check_numeric_answer(processed_player_num, q.answer_type, q.answer)
    
    # --- 2. date answer ---
    elif q.answer_type == AnswerType.DATE:
        # 1. preprocess the player answer
        normalized_date = _normalize_date_text(player_answer)
        # processed_player_date = _preprocess_date_player_ans(normalized_date, hard_cap=1)
        extracted_date = _extract_date_entities(normalized_date)
        # 2. route to evaluator
        return _check_date_answer(extracted_date, q.answer)
    
    # --- 3. catchall for unknown answer-type ---
    result = BaseEvalResults()
    result.is_correct = False
    result.resolution_tier = 'nontext_subrouting_error_invalid_ans_type_combination'
    return result

## 5.2. Subrouter for TEXT type answers
def _route_text_eval(player_answer: str, 
                     q: (ProductionStandard_Green | 
                         ProductionStandard_Blue  |
                         ProductionMCQ_Green      |
                         ProductionMCQ_Blue)):
    """
    Sub-router handling semantic textual answer evaluations
    """
    # 1. Preprocessing (normalize)
    # norm_player_ans = _preprocess_text_player_ans(player_answer)
    
    # 2. MCQ (Mulitple Chocie Questions) evaluator
    if (isinstance(q, ProductionMCQ_Green | ProductionMCQ_Blue)
        and q.question_type == QuestionType.MCQ):
        return check_mcq_answer(player_answer, q)
    
    # 3. FR (Factual Recall) evaluator
    elif (isinstance(q, ProductionStandard_Green| ProductionStandard_Blue) 
          and q.question_type == QuestionType.FR):
        return check_fr_answer(player_answer, q)
    
    # 4. EX (Explanatory) evaluator
    elif (isinstance(q, ProductionStandard_Green| ProductionStandard_Blue) 
          and q.question_type == QuestionType.EX):
        return check_ex_answer(player_answer, q)      

    # 4. Catch-all failsafe
    error_result = BaseEvalResults()
    error_result.is_correct = False
    error_result.resolution_tier = 'text_subrouting_error_invalid_ans_type_combination'
    return error_result

## 5.3 Main router for answer checking

def evaluation_router(raw_player_answer,
                      q: ProductionStandard_Green | 
                         ProductionStandard_Blue  |
                         ProductionMCQ_Green      |
                         ProductionMCQ_Blue) -> BaseEvalResults:
    """
    Main entry point for the Semantic Verification Engine.
    Routes player answers to the appropriate sub-router based on AnswerType.
    """
    # 1. make sure the player answer is str (gateway shield) - guard for switch from CLI
    if not isinstance(raw_player_answer, str):
        raise TypeError(f"Expected string from interface, got {type(raw_player_answer)}.")
    
    # 2. use global normalization (symmetric processing) from `qa_validation` pipeline to match gold ans
    # Note: temporarily mute empty string warnings (needed in validator pipeline but empty player answer is ok)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clean_player_answer = validation_pipeline.normalize_value(raw_player_answer)
    
    # 3. if normalized player answer is None or ""(empty str, ie. player skips with an enter) 
    if not clean_player_answer:
        # return as incorrect answer 
        return BaseEvalResults(
            is_correct=False,
            resolution_tier="empty_submission"
            )
        
    # force linter to recognize player ans always a str
    # (not List[str] as can be expected from normalizer in validation pipeline)
    clean_player_answer = cast(str, clean_player_answer)   
    
    # 4. subrouter for text answers to semantic evaluators
    if q.answer_type == AnswerType.TEXT:
        result = _route_text_eval(clean_player_answer, q)
        return result
    
    # 5. subrouter for non-text answers (numeric, year, date)
    elif q.answer_type in [AnswerType.NUMERIC, AnswerType.YEAR, AnswerType.DATE]:
        result = _route_nontext_eval(clean_player_answer, q)
        return result
    
    # 6. catch all failsafe
    error_result = BaseEvalResults()
    error_result.is_correct = False
    error_result.resolution_tier = 'main_routing_error_invalid_ans_type_combination'
    return error_result
