"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
Common constants and thresholds used by the Answer Evaluators
"""
from pydantic import BaseModel

## 1: Structured evalautors

# mapping for date evaluator
HOLIDAY_MAP ={
    "halloween":"october 31",
    "valentines day": "february 14",
    "valentine's day": "february 14",
    "christmas": "december 25",
    "christmas eve": "december 24",
    "new years eve": "december 31",
    "new year's eve": "december 31"
}
## 2: Constants & Thresholds for semantic evaluators

# COMMON setting (FR, MCQ only)
FUZZY_THRESHOLD = 0.85

# MCQ (Multiple Choice Questions)
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
    
# FR (Factual Recall questions)
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
