"""
Standardized Schemas for the Harry Potter Trivia Project.

-   Extends BaseQuestion by adding `answer_variations`, which are required
    for training the semantic answer checker (SBERT). Used as the
    `response_schema` in the Gemini API configuration.
"""

from typing import List
from typing_extensions import TypedDict
from ds_utils.ds_constants import QuestionType

# Basic schema for all question types to inherit
class BaseQuestion(TypedDict):
    """
    The foundational schema defining fields common to all trivia question types.
    
    All specific question formats (Standard, MCQ) inherit from this structure
    to ensure core metadata (category, difficulty, sources) is always present.
    """
    question_type: QuestionType
    category: str
    difficulty: str
    question: str
    answer: str
    source_reference: str
    source_quote: str

# FR and EX inherit the schema, add answer_variations, for API respnose schema
class StandardQuestion(BaseQuestion):
    """
    Schema for Explanatory (EX) and Factual Recall (FR) questions.
    
    Extends BaseQuestion by adding `answer_variations`, which are required
    for training the semantic answer checker (SBERT). Used as the
    `response_schema` in the Gemini API configuration.
    """
    answer_variations: List[str]

# MCQ passes the BaseQuestion scheam directly as the API response schema    
class MCQuestion(BaseQuestion):
    """
    Schema for Multiple Choice (MCQ) questions.
    
    Currently identical to BaseQuestion, as the options are embedded directly 
    within the `question` string (e.g., "Question text? Option A, Option B, ...")
    in the 'master' prompt format.
    
    The class is defined explicitly to allow for future expansion (e.g., extracting options 
    into a list) without breaking EX/FR logic.
    """
    pass
