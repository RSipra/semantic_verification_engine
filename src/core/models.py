"""
Project: SVE (ref implementation: Harry Potter Trivia)
Pydantic Schemas (Phase 2+)
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from ds_utils.ds_constants import QuestionType, QuestionSource

# Basic schema for all question types to inherit
class BaseQuestion(BaseModel):
    """
    The foundational schema defining fields common to all trivia question types.
    
    All specific question formats (Standard, MCQ) inherit from this structure
    to ensure core metadata (category, difficulty, sources) is always present.
    """
    question_type: QuestionType
    question_source: QuestionSource
    category: Optional[str] = None
    difficulty: Optional[str] = None
    question: str
    answer: str
    hint_1: str
    hint_2: Optional[str] = None
    hint_3: Optional[str] = None
    explanation: str

# FR and EX inherit the schema, add answer_variations, for API respnose schema
class StandardQuestion(BaseQuestion):
    """
    Core Schema for Explanatory (EX) and Factual Recall (FR) questions. 
    Used for Legacy upgrades.
    
    Extends BaseQuestion by adding `answer_variations`, which are required
    for training the semantic answer checker (SBERT). Used as the
    `response_schema` in the Gemini API configuration.
    
    Does not require source grounding, making it ideal for grandfathering in
    existing data that lacks specific book references.
    """
    answer_variations: List[str]

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
        Cross-field validation to ensure logical consistency.
        
        This check runs after the object is fully assembled (mode='after'). 
        We use a model_validator here because the check requires access to 
        both the 'answer' (defined in BaseQuestion) and the 'options' 
        (defined in MCQuestion). If the correct answer is not in the list 
        of choices, the record is rejected as 'unplayable.'
        """
        if self.answer not in self.mcq_options:
            raise ValueError(f"Correct answer '{self.answer}' must be one of the options.")
        return self

class SyntheticStandard(StandardQuestion):
    """
    STRICT schema for new FR/EX questions. 
    Enforces 'source_reference' and 'source_quote' to ensure
    high-quality grounding and prevent duplicates in the Content Factory.
    """
    source_reference: str
    source_quote: str

class SyntheticMCQ(MCQuestion):
    """
    STRICT schema for new MC questions. 
    Enforces 'source_reference' and 'source_quote' to ensure
    high-quality grounding and prevent duplicates in the Content Factory.
    """
    source_reference: str
    source_quote: str
