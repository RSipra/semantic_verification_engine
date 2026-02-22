"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================
Common constants used across the data science scripts and notebooks.
"""
from enum import Enum

# --- CONFIGURATION & CONSTANTS ---

# --- MAIN KEYWORD IDENTIFICATION ---
PRIORITY_1_KEYWORDS = {'what', 'name', 'who', 'where', 'when', 'which', 'how', 'why'}
PRIORITY_2_KEYWORDS = {'be', 'do', 'can', 'have', 'would',
                       'could', 'should', 'true', 'false'}

# Month names and abbreviations for date detection to categorize answers
MONTH_NAMES = {
    'january', 'jan', 'february', 'feb', 'march', 'mar', 'april', 'apr',
    'may', 'june', 'jun', 'july', 'jul', 'august', 'aug', 'september', 'sep',
    'october', 'oct', 'november', 'nov', 'december', 'dec'
}

# The combined list will be built from these clean sources
INTERROGATIVE_KEYWORDS_LIST  = list(PRIORITY_1_KEYWORDS) + list(PRIORITY_2_KEYWORDS)

# --- QUESTION CLASSIFICATION KEYWORDS ---
# These sets are used by the categorize_question helper function to assign a final category.

# Keywords that explicitly signal a Factual Recall question
FACTUAL_RECALL_KEYWORDS = {'what', 'who', 'which', 'where', 'when', 'name'}

# Keywords that explicitly signal an Explanatory question
EXPLANATORY_KEYWORDS = {'why'}

# Keywords that explicitly signal a Yes/No question
YES_NO_KEYWORDS = {'be','do', 'can', 'is', 'are', 'was', 'were', 'did', 'true', 'false'}

# N-grams that identify a "how" question as Factual Recall
FACTUAL_HOW_NGRAMS = {'how many', 'how old', 'how long', 'how much'}

# Phrases that indicate a Multiple Choice Question
MCQ_INDICATOR_PHRASES = {
    "which of the following",
    "which of these",
    "which one of the following",
    "which one of these",
    "select the correct",
    "choose the best answer",
    "choose the one that",
    "identify the option that",
    "all of the following are",
    "which statement is true",
    "which statement is false",
    "who of the following",
    "who among the following"
}

# A general regex pattern to find MCQ-like formats (e.g., a list of choices)
MCQ_FORMAT_PATTERN = r'[:?]\s*.*,\s*.*\s*or\s*.*'

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

class DataTier(str, Enum):
    """
    Enum class to distinguish between legacy and synthetic questions source.
    """
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    