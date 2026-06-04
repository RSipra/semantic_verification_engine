"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) -> Data Transfer Objects 
                          Integration / Boundary DTOs
-----------------------------------------------------------------------
This module defines internal data contracts used to represent evaluation
outputs produced by the Evaluator layer.

The DTOs in this module are not used for data ingestion or external parsing.
They are constructed directly by Evaluator components as the final
representation of computed evaluation state.

Two categories of structures exist:

1. Evaluation Result DTOs:
   - BaseEvalResults
   - MCQEvalResults
   - FREvalResults
   - EXEvalResults

   These represent structured outputs of evaluator logic (e.g. similarity
   scoring, rule-based decisions, and hybrid resolution logic).
   They are internal evaluator-owned artifacts and are always constructed
   in-code, not from external input.
   NOTE: This evaluation DTO includes runtime and debug metadata for tracer visibility.
   Some fields (e.g. execution_time_sec, model_used, reasoning) may be migrated
   to a dedicated tracing layer in future iterations once observability is separated.

2. LLM Schema Contract:
   - LLMJudgeResponse

   This defines the structured output format used in LLM API calls during
   inference-time evaluation. It is not an evaluation result itself, but a
   generation-time contract that enforces consistent reasoning, classification,
   and UX-facing responses from the model.

Design principle:
- DTOs represent evaluator-owned outputs only
- No parsing, coercion, or input normalization occurs in this layer
- Validation focuses strictly on structural integrity and type correctness
-----------------------------------------------------------------------
"""

from pydantic import BaseModel, Field, model_validator
from core.constants import QuestionType, AnswerType

## --- LLM Response Schema ---

# LLM response pydantic model (EX, FR)
class LLMJudgeResponse(BaseModel):
    """
    Structured output from the LLM-based evaluation step for subjective or semantic
    question types (e.g., FR and EX).

    This model enforces a deterministic output schema for LLM judgment, separating
    reasoning from final classification to reduce premature binary decision-making.

    Attributes:
        reasoning (str):
            Step-by-step justification of the evaluation outcome.
            Should explicitly compare expected vs provided answer semantics,
            including entity-level and contextual alignment.

        mc_dialogue (str):
            A concise, in-character response from the quiz host.
            Used for UX layer feedback and should remain independent of correctness logic.

        is_correct (bool):
            Final binary judgment of correctness.
            Must only be derived after reasoning is fully established.
            True only when semantic equivalence and entity alignment are satisfied.
    """
    # ordered to push model to think before assigning boolean
    evaluation_reasoning: str = Field(description=
                           "Step-by-step logical proof of why the answer fails or passes the strict criteria.")
    quiz_host_response: str = Field(description=
                             "A short, 1-sentence in-character reaction from the quiz host.")
    # The boolean comes LAST, after the logic is established
    is_correct: bool = Field(description=
                             "True ONLY if the reasoning proves absolute semantic and entity alignment.")


## --- Structured output: Answer Evaluation Results ---
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
    execution_time_sec: float = 0.0  # full evaluation latency
    
    # TODO: move float rounding into evaluator layer.
    # to keep DTOs as passive data contracts.
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
    matched_answer_variation: bool = False  # whether the player answer matched a variation (shorthand) rather than the main gold answer (telemetry placeholder)
    # execution_time_sec: float = 0.0

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
    matched_answer_variation: bool = False  # flag if player answer matched variation instead of main answer
    matched_entity_ref: str | None = None     # alias / synonym matched from semantic_entity_refs col
    boost_applied: float = 0.0       # entitry ref boost for ambiguous similarity scores
    final_boosted_score: float = 0.0 # base_sim_score + boost_applied
    llm_model_used: str | None = None
    quiz_host_response: str = ""
    evaluation_reasoning: str = ""
    llm_eval_time_sec: float = 0.0
    # execution_time_sec: float = 0.0

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
    matched_answer_variation: bool = False
    nli_label: str = ""
    nli_confidence: float = 0.0
    llm_model_used: str | None = None
    quiz_host_response: str = ""
    evaluation_reasoning: str = ""
    llm_eval_time_sec: float = 0.0
    # execution_time_sec: float = 0.0

# Result wrapper for controller
class TurnResult(BaseModel):
    """Per question turn wrapper around Evaluation results to be
    compiled for the session by the controller"""
    question_idx: int               # sequence id
    question_master_id: str         # global question identifier
    question_type: QuestionType
    answer_type: AnswerType
    correct_answer: str
    player_answer: str
    evaluation: BaseEvalResults 
