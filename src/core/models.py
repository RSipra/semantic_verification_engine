""""
Project: SVE (ref implementation: Harry Potter Trivia)
Pydantic Schemas (Phase 2+)
"""
import math
import json
import hashlib
import base64
from typing import List, Optional, Self, Dict, Literal, TYPE_CHECKING, Any
from pydantic import BaseModel, field_validator, Field, model_validator, ConfigDict, ValidationInfo
import numpy as np
from notebook_support.ds_constants import QuestionType, QuestionSource, DataTier, AnswerType

# Basic schema for all question types to inherit
class BaseQuestion(BaseModel):
    """
    The foundational schema defining fields common to all trivia question types.
    
    All specific question formats (Standard, MCQ) inherit from this structure
    to ensure core metadata (category, difficulty, sources) is always present.
    """
    # makes enums serialize as their values
    model_config = ConfigDict(use_enum_values=True)

    question_type: QuestionType
    question_source: QuestionSource
    question: str
    answer: str
    answer_variations: List[str]
    hint_1: str
    hint_2: str
    hint_3: str
    explanation: str
    semantic_entity_refs: List[str]
    semantic_lore_concepts: List[str]
    
    @field_validator('*', mode='before')
    @classmethod
    def convert_numpy_arrays(cls, v):
        """Convert any numpy array field to a Python list"""
        if isinstance(v, np.ndarray):
            return v.tolist()
        return v
    
    @model_validator(mode='after')
    def check_answer_variations(self):
        """check list lengths for answer_variations based on qtype
        """
        ans_var = self.answer_variations
        q_type = self.question_type
        if len(ans_var) < 1:
            raise ValueError('Must have at least 1 answer variation')

        if q_type == QuestionType.EX and len(ans_var)>3 :
            raise ValueError('EX questions must have at most 3 answer variations')
        return self

class PipelineMetadata(BaseModel):
    """
    Fields that track how a question was generated.
    Present at Bronze and Silver, shed at Gold.
    """
    generation_model: str
    generation_prompt_version: Optional[Dict[str, str]] = Field(default=None)
    lex_enrich_prompt_version: str
    semantic_enrich_prompt_version: str
    
    @field_validator('generation_prompt_version', mode='before')
    @classmethod
    def deserialize_prompt_version(cls, v):
        """
        Parquet round-trip stores this as a JSON string.
        Deserialize back to dict on load.
        """
        if isinstance(v, str):
            return json.loads(v)
        return v  # already a dict or None, pass through

# MCQ mixing to be added to MCQ classes along with BaseQuestion to decouple 
# core fields so GoldMCQ doesn't indirectly inherit Silver audit fields that were shed.
class MCQuestion(BaseModel):
    """
    Mixin that adds MCQ-specific fields and validation to any tier schema.
    Inherits from BaseModel (not BaseQuestion) so it can be composed cleanly
    across all tiers without dragging a second BaseQuestion chain into the
    class hierarchy. Always paired with a tier-specific parent:
        LegacyMCQ(LegacyStandard, MCQuestion)
        SilverMCQ(SilverStandard, MCQuestion)
        GoldMCQ(GoldStandard, MCQuestion)
    """
    # TYPE HINTING ONLY: Prevents Pylance 'unknown attribute' errors.
    # At runtime, Pydantic ignores this. The @model_validator(mode='after')
    # safely accesses `self.answer` because the final composed class
    # (e.g. GoldMCQ) will inherit `answer` directly from BaseQuestion.
    # error happens because changed to a MCQ to mixin instead of inheriting
    # BaseQuestion anymore

    if TYPE_CHECKING:
        answer: str
    mcq_options: List[str] = Field(..., min_length=4, max_length=4)

    # Ensure that the answer is one of the options
    @model_validator(mode='after')
    def check_answer_in_options(self) -> 'MCQuestion':
        """
        Validates that the canonical answer is exactly one of the options.
        """
        clean_answer = self.answer.strip()
        clean_options = [opt.strip() for opt in self.mcq_options]

        if clean_answer not in clean_options:
            raise ValueError(f"Correct answer '{self.answer}' must be one of the options.")
        return self

class SyntheticStandard(BaseQuestion, PipelineMetadata):
    """
    STRICT schema for new FR/EX questions. 
    Enforces 'source_reference' and 'source_quote' to ensure
    high-quality grounding and prevent duplicates in the Content Factory.
    """
    # TODO (full dev): rename to `syn_id`
    temp_qid: str = Field(
        description="Notebook tracer artifact. In main dev, the generation pipeline "
                    "should emit this as 'syn_id' (Run/Batch/Job/QID) natively to avoid "
                    "schema transitions between Bronze and Silver."
    )
    llm_predicted_category: str
    llm_predicted_difficulty: str
    source_reference: str
    source_quote: str

    @model_validator(mode='after')
    def validate_source_metadata(self):
        """Make sure required source meta data is present
        """
        if self.source_reference is None:
            raise ValueError("Record is missing its grounding source_reference \
                             entry required for deduplication")
        if self.source_quote is None:
            raise ValueError("Record is missing its grounding source_quote entry \
                required for deduplication")
        return self

    @model_validator(mode='after')
    def validate_synthetic_lineage(self):
        """Confirm the synthetic questions have the generation prompt version included"""
        if self.question_source == "synthetic" and self.generation_prompt_version is None:
            raise ValueError(
                "Synthetic questions must include a generation_prompt_version dictionary.")
        return self

class SyntheticMCQ(MCQuestion, SyntheticStandard):
    """
    STRICT schema for new multiple-choice questions (MCQ). 
    Inerits MCQ behavior from MCQ_question and full Synthetic
    columns from Synthetic standard.
    """
    pass

class LegacyStandard(BaseQuestion, PipelineMetadata):
    """
    Inherits base question and adds legacy identifier
    """
    original_question_id: int

class LegacyMCQ(MCQuestion, LegacyStandard):
    """
    STRICT schema for new multiple-choice questions (MCQ). 
    Inerits MCQ behavior from MCQ_question and full Legacy
    columns from Legacy standard.
    """
    pass

class EnrichmentFlag(BaseModel):
    """
    Represents a specific diagnostic finding from the LLM Enrichment Audit.
    
    This class captures granular failures or warnings identified during the 
    LLM judge validation of synthetically generated fields (hints, explanation, 
    answer variations). It allows for targeted debugging of the enrichment prompts
    (lexical enrichment, semantic context variations) within the generation pipeline
    """
    column_name: str
    severity: Literal["error", "warning"]
    flag_notes: str

# Audit layer and system invariant (stores metadata for traceability)
class SilverStandard(BaseQuestion, PipelineMetadata):
    """
    The Silver Tier schema for Standard (FR/EX) questions.
    Captures full audit traces, embeddings, and model lineage.
    """
    model_config = ConfigDict(populate_by_name=True) #standardize names to clean python format

    # required (check 1. confirm master_id is the right shape / format)
    master_id: str= Field(
        min_length=8,
        max_length=8,
        pattern=r'^[A-Za-z0-9_-]+$',
        description="Deterministic 8-char Base64 URL-safe hash"
    )
    # Traceability identifiers
    original_question_id: Optional[int] = None
    syn_id: Optional[str] = None

    # SBERT embeddings (vector data)

    question_embeddings: List[float]
    answer_embeddings: List[float]
    answer_variations_embeddings: List[List[float]]
    source_quote_embeddings: Optional[List[float]] = None

    # Generation pipeline metadata (None for Legacy)
    llm_predicted_category: Optional[str] = None
    llm_predicted_difficulty: Optional[str] = None
    source_reference: Optional[str] = None
    source_quote: Optional[str] = None

    # Validation: Synthetic RAG-Triad check with LLM Judge (None for Legacy)
    eval_source_quote_match: Optional[str] = None
    eval_ans_grounding: Optional[str] = None
    eval_ques_logic: Optional[str] = None
    # LLM judge assigns codes 0,1,2 (0 and 1 are acceptable, 2 is fail and should not be observed)
    score_source_quote_match: Optional[Literal[0, 1]] = None
    score_ans_grounding: Optional[Literal[0, 1]] = None
    score_ques_logic: Optional[Literal[0, 1]] = None

    # Validation stage 3: Alignment (only accepted records, so no False)
    ans_variations_valid: Optional[Literal[True]] = None
    # validation of questions answer types using Gen-LLM assigned categories (only Synthetic)
    alignment_valid: Optional[Literal[True]] = None
    alignment_reason: Optional[str] = None

    # Validation of enrichment cols (hints, ans var, explanation) with LLM Judge (optional for Synthetic)
    enrich_audit_status: Optional[Literal["pass","fail"]] = None
    enrich_audit_flags: Optional[List[EnrichmentFlag]] = Field(default_factory=list)
    enrich_judge_reasoning: Optional[str] = None

    # Validation pipeline metadata
    sbert_model: str        #required -> system invariant
    llm_judge_model: str    # each question source has atleast one LLM judge pass
    judge_RAGtriad_prompt_version: Optional[str] = None
    judge_enrich_col_prompt_version: Optional[str] =None
    
    # validation: deduplication of synthetic vs. existing Gold
    dedupe_action: Optional[str] = None
    closest_legacy_id: Optional[int] = None
    max_similarity_score: Optional[float] = None
    
    @field_validator('enrich_audit_flags', mode='before')
    @classmethod
    def deserialize_audit_flags(cls, v):
        """
        Deserializes 'enrich_audit_flags' from a JSON string back to a list of dicts
        after a Parquet round-trip. Pydantic then coerces each dict into an EnrichmentFlag object.
        Passes through unchanged if already a list or None.
        """
        if isinstance(v, str):
            return json.loads(v)
        if isinstance(v, np.ndarray):
            return json.loads(''.join(v.tolist()))
        return v

    # check 2. check deterministic math of the master_id corresponds to question data
    @model_validator(mode='after')
    def verify_master_id(self):
        """
        Mathematically verifies that the master_id perfectly matches the deterministic 
        MD5 base64url hash of the question payload (ADR-P2-021). Prevents referential 
        corruption by ensuring IDs cannot be accidentally reassigned or scrambled during merges.
        """
        # 1. Recreate the exact payload from assign_master_ids
        payload = f"{self.question_type}_{self.question}_{self.answer}"

        # 2. Recalculate the expected hash
        hash_bytes = hashlib.md5(payload.encode('utf-8')).digest()
        expected_id = base64.urlsafe_b64encode(hash_bytes).decode('utf-8').rstrip('=')[:8]

        # 3. Drop the hammer if they don't match
        if self.master_id != expected_id:
            raise ValueError(
                f"CRITICAL: master_id mismatch! "
                f"Expected {expected_id} for payload '{payload}', but got {self.master_id}.")
        return self

    @model_validator(mode="after")
    def validate_origin_integrity(self) -> Self:
        """
        Enforces strictness for synthetic data while allowing 
        nulls for legacy bootstrap data.
        """
        # 1. Define required fiels for each question source
        if self.question_source == QuestionSource.SYNTHETIC:
            check_map = {
                "syn_id": self.syn_id,
                "llm_predicted_category": self.llm_predicted_category,
                "llm_predicted_difficulty": self.llm_predicted_difficulty,
                "source_reference" : self.source_reference,
                "source_quote": self.source_quote,
                "ans_variations_valid": self.ans_variations_valid,
                "eval_source_quote_match": self.eval_source_quote_match,
                "eval_ans_grounding": self.eval_ans_grounding,
                "eval_ques_logic": self.eval_ques_logic,
                "score_source_quote_match": self.score_source_quote_match,
                "score_ans_grounding": self.score_ans_grounding,
                "score_ques_logic": self.score_ques_logic,
                "alignment_valid": self.alignment_valid,
                "alignment_reason": self.alignment_reason,
                "dedupe_action": self.dedupe_action,
                "closest_legacy_id" : self.closest_legacy_id,
                "max_similarity_score" : self.max_similarity_score
            }
        elif self.question_source == QuestionSource.LEGACY:
            check_map = {
                "original_question_id": self.original_question_id,
                "enrich_audit_status": self.enrich_audit_status,
                "enrich_audit_flags": self.enrich_audit_flags,
                "enrich_judge_reasoning": self.enrich_judge_reasoning,
                "llm_judge_model": self.llm_judge_model,
                "judge_enrich_col_prompt_version": self.judge_enrich_col_prompt_version
            }
        else:
            return self # safety 
        # 2. record which fields are missing in a list
        missing = [field_name for field_name, value in check_map.items() if value is None]
        # 3. raise error message
        if missing:
            raise ValueError(
                f"Validation Failed for {self.question_source} record: "
                f"The following required fields are missing/null: {missing}"
            )
        return self
    
    @model_validator(mode='after')
    def check_at_least_one_judge_pass(self) -> 'SilverStandard':
        """Each question source (legacy, synthetic) has run it's required LLM pass"""
        if not self.judge_RAGtriad_prompt_version and not self.judge_enrich_col_prompt_version:
            row_id = self.syn_id or self.original_question_id
            raise ValueError(
                f"Row {row_id} is missing both judge prompt versions... "
            )
        return self


class SilverMCQ(SilverStandard, MCQuestion):
    """
    Core schema for Silver Multiple Choice (MCQ) questions.
    Inherits core fields from SilverStandard and requires exactly 4 options.
    Validation ensures the designated correct answer is present within the options. 
    """
    mcq_distractors_embeddings: List[List[float]]

    # validation results (for only accepted questions to pass)
    mcq_presence_valid: Literal[True]
    mcq_distractors_valid: Literal[True]
    mcq_margin_score: float
    mcq_closest_distractor: str

# runtime projection of Silver for handoff
class GoldStandard(BaseQuestion):
    """ Final gold FR, EX schema """ 
    # ensure that shedded columns are dropped
    model_config = ConfigDict(extra='ignore')
    # required (check 1. confirm master_id is the right shape / format)
    master_id: str= Field(
        min_length=8,
        max_length=8,
        pattern=r'^[A-Za-z0-9_-]+$',
        description="Deterministic 8-char Base64 URL-safe hash"
    )

    # SBERT embeddings (vector data)
    question_embeddings: List[float]
    answer_embeddings: List[float]
    answer_variations_embeddings: List[List[float]]
    source_quote_embeddings: Optional[List[float]] = None

    # for traceability only 
    original_question_id: Optional[int] = None
    syn_id: Optional[str] = None

    # optional because they are null for Legacy
    source_reference: Optional[str] = None
    source_quote: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def shed_rectangular_nulls(cls, data: dict) -> dict:
        """
        Data Engineering Bridge: Pandas DataFrames are perfectly rectangular, 
        meaning FR/EX rows will inevitably contain empty 'mcq_options' columns.
        This intercepts the raw Pandas dictionary and sheds any empty fields 
        before the strict `extra="forbid"` check is applied.
        """
        clean_data = {}
        for k, v in data.items():
            # Keep the key if it has a real value
            # Drop it if it is None or a Pandas NaN (float nan).
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                clean_data[k] = v
                
        return clean_data
    
    # check 2. check deterministic math of the master_id corresponds to question data
    @model_validator(mode='after')
    def verify_master_id(self):
        """
        Mathematically verifies that the master_id perfectly matches the deterministic 
        MD5 base64url hash of the question payload (ADR-P2-021). Prevents referential 
        corruption by ensuring IDs cannot be accidentally reassigned or scrambled during merges.
        """
        # 1. Recreate the exact payload from assign_master_ids
        payload = f"{self.question_type}_{self.question}_{self.answer}"

        # 2. Recalculate the expected hash
        hash_bytes = hashlib.md5(payload.encode('utf-8')).digest()
        expected_id = base64.urlsafe_b64encode(hash_bytes).decode('utf-8').rstrip('=')[:8]

        # 3. Drop the hammer if they don't match
        if self.master_id != expected_id:
            raise ValueError(
                f"CRITICAL: master_id mismatch! "
                f"Expected {expected_id} for payload '{payload}', but got {self.master_id}.")
        return self

class GoldMCQ(GoldStandard, MCQuestion):
    """ Final Gold MCQ schema. Combines Gold-tier metadata 
    with Silver-tier MCQ validation logic. """

    mcq_distractors_embeddings: List[List[float]]

# Context Refinery model (Gold + Context Features) - for development / experimentation
class ProductionStandard_Green(GoldStandard):
    """
    Full production FR, EX schema with
    feature experimentation
    (Gold + context refinery features)
    """ 
    # ensure that shedded columns are dropped
    model_config = ConfigDict(extra='ignore', arbitrary_types_allowed=True) # for tensors

    # descriptive features
    question_length: int
    answer_length: int
    answer_type: AnswerType
    question_tokens: List[str]
    answer_tokens: List[str]
    combined_unique_tokens: List[str]
    main_keyword: str
    
    # NER features to come

    # tensors calculated upfront during runtime warmup for session
    # NOTE: Type `Any` is used to bypass Pydantic's internal validation
    # checks for non-standard types (torch.Tensor), ensuring near-instant
    # `Question` object instantiation during the warmup loop.
    question_embeddings_tensor: Optional[Any] = None
    answer_embeddings_tensor: Optional[Any] = None
    answer_variations_embeddings_tensor_matrix:  Optional[Any] = None
    
    @field_validator(
        "question_embeddings_tensor",
        "answer_embeddings_tensor",
        "answer_variations_embeddings_tensor_matrix",
        mode="after"
    )
    @classmethod
    def validate_runtime_tensors(cls, v: Any, info: ValidationInfo) -> Any:
        """
        Validates that tensors are present, are numpy arrays, 
        and match the SBERT 384-dimension requirement.
        """
        # 1. Grab the field name or default to an empty string to keep type checkers happy
        fname = info.field_name or ""

        if v is None:
            raise ValueError(f"CRITICAL: {fname} is missing.")

        # 2. Use specific suffix checking
        if fname.endswith("_matrix"):
            if v.ndim != 2 or v.shape[1] != 384:
                raise ValueError(f"Matrix {fname} must be (N, 384). Got {v.shape}")
        else:
            if v.shape != (384,):
                raise ValueError(f"Vector {fname} must be (384,). Got {v.shape}")

        return v

# Context Refinery model (Gold + Context Features) - for development / experimentation
class ProductionMCQ_Green(ProductionStandard_Green, MCQuestion):
    """
    Full production MCQ schema with
    feature experimentation
    (Gold + context refinery features)
    """ 
    # tensors calculated upfront during runtime warmup for session
    # NOTE: Type `Any` is used to bypass Pydantic's internal validation
    # checks for non-standard types (torch.Tensor), ensuring near-instant
    # `Question` object instantiation during the warmup loop.
    mcq_distractors_embeddings_tensor_matrix : Optional[Any] = None
    
# stable serving model for runtime (lean, mirror version of Green dataset)
class ProductionStandard_Blue(GoldStandard):
    """
    Runtime ready lean production FR, EX schema
    (required Gold + context refinery features only)
    """
    question_length: int
    answer_length: int
    answer_type: AnswerType
    
    # tensors calculated upfront during runtime warmup for session
    question_embeddings_tensor: Optional[Any] = None
    answer_embeddings_tensor: Optional[Any] = None
    answer_variations_embeddings_tensor_matrix:  Optional[Any] = None

class ProductionMCQ_Blue(ProductionStandard_Blue, MCQuestion):
    """
    Runtime ready lean production MCQ schema
    (required Gold + context refinery features)
    """ 
    # tensors calculated upfront during runtime warmup for session
    mcq_distractors_embeddings_tensor_matrix : Optional[Any] = None    

## Model routing

# routing for models at runtime (devlopment vs. stable modes)
RUNTIME_REGISTRY = {
    "dev": {
        QuestionType.EX : ProductionStandard_Green,
        QuestionType.FR : ProductionStandard_Green,
        QuestionType.MCQ: ProductionMCQ_Green
    },
    "stable":{
        QuestionType.EX : ProductionStandard_Blue,
        QuestionType.FR : ProductionStandard_Blue,
        QuestionType.MCQ: ProductionMCQ_Blue
    }
}

# routing for the `qa_validation_pipeline` in Content Factory    
VALIDATION_REGISTRY = { 
    QuestionSource.LEGACY:{
        DataTier.BRONZE:{
            QuestionType.EX : LegacyStandard,
            QuestionType.FR : LegacyStandard,
            QuestionType.MCQ: LegacyMCQ 
            }, 
        DataTier.SILVER:{ 
            QuestionType.EX : SilverStandard,
            QuestionType.FR : SilverStandard,
            QuestionType.MCQ: SilverMCQ },
        DataTier.GOLD:{ 
            QuestionType.EX : GoldStandard,
            QuestionType.FR : GoldStandard,
            QuestionType.MCQ: GoldMCQ
            }
        },
    QuestionSource.SYNTHETIC:{
        DataTier.BRONZE:{
            QuestionType.EX : SyntheticStandard,
            QuestionType.FR : SyntheticStandard,
            QuestionType.MCQ: SyntheticMCQ 
            }, 
        DataTier.SILVER:{ 
            QuestionType.EX : SilverStandard,
            QuestionType.FR : SilverStandard,
            QuestionType.MCQ: SilverMCQ
            }, 
        DataTier.GOLD:{
            QuestionType.EX : GoldStandard,
            QuestionType.FR : GoldStandard,
            QuestionType.MCQ: GoldMCQ
            }
        }
    }
