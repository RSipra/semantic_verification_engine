""""
Project: SVE (ref implementation: Harry Potter Trivia)
Pydantic Schemas (Phase 2+)
"""
from typing import List, Optional, Self
from pydantic import BaseModel, field_validator, Field, model_validator, ConfigDict
import numpy as np
from ds_utils.ds_constants import QuestionType, QuestionSource, DataTier

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

# MCQ passes the BaseQuestion scheam directly as the API response schema    
class MCQuestion(BaseQuestion):
    """
    Core schema for Multiple Choice (MCQ) questions.
    Inherits core fields from BaseQuestion and requires exactly 4 options.
    Validation ensures the designated correct answer is present within the options.
    """
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

class SyntheticStandard(BaseQuestion):
    """
    STRICT schema for new FR/EX questions. 
    Enforces 'source_reference' and 'source_quote' to ensure
    high-quality grounding and prevent duplicates in the Content Factory.
    """
    temp_qid: str
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

class SyntheticMCQ(MCQuestion, SyntheticStandard):
    """
    STRICT schema for new MC questions. 
    Inerits MCQ behavior from MCQ_question and full Synthetic
    columns from Synthetic standard.
    """
    pass

class LegacyStandard(BaseQuestion):
    """
    """
    original_question_id: int

class LegacyMCQ(MCQuestion, LegacyStandard):
    """
    """
    pass

class SilverStandard(BaseQuestion):
    """_summary_ """ 

    # for traceability only 
    original_question_id: Optional[int] = None
    temp_qid: Optional[str] = None

    # optional because they are null for Legacy 
    llm_predicted_category: Optional[str] = None
    llm_predicted_difficulty: Optional[str] = None
    source_reference: Optional[str] = None
    source_quote: Optional[str] = None
    question_embeddings: List[float]
    answer_embeddings: List[float]

    @model_validator(mode="after")
    def validate_source_specific_ids(self) -> Self: 
        """_x_ """
        if self.question_source == QuestionSource.LEGACY: 
            if self.original_question_id is None: 
                raise ValueError("Legacy records must have original_question_id.")
        if self.question_source == QuestionSource.SYNTHETIC: 
            if self.temp_qid is None: 
                    raise ValueError("Synthetic records must have temp_qid.")
        return self 

class SilverMCQ(SilverStandard): 
    """_summary_ :param Silver: _description_ """ 

    mcq_options: List[str] = Field(..., min_length=4, max_length=4)

    # Ensure that the answer is one of the options 
    @model_validator(mode='after') 
    def check_answer_in_options(self)-> Self: 
        """ Cross-field validation to ensure logical consistency. 
        This check runs after the object is fully assembled (mode='after'). 
        The model_validator is used here because the check requires access to 
        both the 'answer' (defined in BaseQuestion) and the 'options' 
        (defined in SilverMCQuestion). If the correct answer is not in the 
        list of choices, the record is rejected as 'unplayable.' """ 

        if self.answer not in self.mcq_options: 
            raise ValueError(f"Correct answer '{self.answer}' must be one of the options.")
        return self 

class GoldStandard(BaseQuestion):
    """ Final gold FR, EX schema """ 

    # ensure that shedded columns are dropped (e.g. llm_predicted_category) 
    model_config = ConfigDict(extra="forbid")

    # required 
    gold_id: int
    question_embeddings: List[float]
    answer_embeddings: List[float]

    # for traceability only 
    original_question_id: Optional[int] = None

    # optional because they are null for Legacy
    source_reference: Optional[str] = None
    source_quote: Optional[str] = None

class GoldMCQ(GoldStandard, SilverMCQ): 
    """ Final Gold MCQ schema. Combines Gold-tier metadata 
    with Silver-tier MCQ validation logic. """

    mcq_options: List[str] = Field(..., min_length=4, max_length=4)

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
