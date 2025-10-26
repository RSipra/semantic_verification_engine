"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================
Common constants used across the data science scripts and notebooks.
"""

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
