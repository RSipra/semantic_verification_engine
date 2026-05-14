"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================
Common constants used across the SVE systems
"""
from enum import Enum


class AnswerType (str, Enum):
    """
    Enum definition for answer_type categorical colum in Production 
    dataset for pydantic checks
    """
    TEXT = "text"
    DATE = "date"
    NUMERIC = "numeric"
    YEAR = "year"

# Standardized book names (as prefixe to chapter numbers in file names)
class Book(str, Enum):
    """ 
    An enumeration for the main books in the harry poter series.

    This class provides a fixed, type-safe set of constants used throughout
    the game for player house selection, validation, and related logic.
    By inheriting from `str`, members can also be treated as strings directly.
    """
    BOOK_3 = "prisoner_of_azkaban_"
    BOOK_4 = "goblet_of_fire_"
    BOOK_7 = "deathly_hallows_"

# standardized question types (for LLM model json response schema)
class QuestionType(str, Enum):
    """
    Enumeration of supported trivia question types for the Harry Potter project.

    This class defines the strict string values used across the generation pipeline,
    including Prompt Templates, JSON Schemas, and API validation logic.
    
    Inheriting from `str` allows members to be serialized directly to JSON
    and used in string comparisons (e.g., `if q_type == "EX"`).

    Attributes:
        EX: Explanatory questions focusing on reasoning ("Why" or "How").
        MCQ: Multiple Choice questions with distractors (Combined format).
        FR: Factual Recall questions with direct, short answers.
        YN: Yes/No or True/False question with answers that contain these keywords 
    """
    EX = "EX"
    MCQ = "MCQ"
    FR = "FR"
    YN = "YN"
    
    @property
    def label(self) -> str:
        """Human readable labels for the question types"""
        labels = {
            QuestionType.EX: "Explanatory (Why/How)",
            QuestionType.MCQ: "Multiple Choice (MCQ)",
            QuestionType.FR: "Factual Recall (FR)",
            QuestionType.YN: "Yes/No or True/False",
        }
        return labels[self]

class QuestionSource(str, Enum):
    """
    Enum class to distinguish between legacy and synthetic questions source.
    """
    LEGACY = "legacy"
    SYNTHETIC = "synthetic"


    