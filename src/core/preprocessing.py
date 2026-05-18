"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) -> Common preprocessing shared by Offline and
                          Runtime sysetms
-----------------------------------------------------------------------


"""
import string
import unicodedata
import warnings
from typing import Optional
import regex as re
import pandas as pd
import numpy as np

## General helpers:

def count_clean_words(text) -> int:
    """
    Returns the number of clean words (ignoring punctuation) in a single string.
    Safely handles None, NaN, or non-string inputs.
    """
    if pd.isna(text) or not isinstance(text, str):
        return 0
    return len(re.findall(r'\b\w+\b', text))

## 1: Normalization 

# helper to stripping white spaces
def _remove_whitespace(text: str) -> str:
    """strip leading / trailing whitespaces"""
    return text.strip()

# helper for changing all text to lower case
def _to_lower(text: str) -> str:
    """convert str to lower case"""
    return text.lower()

# helper to remove punctuation
def _remove_punctuation(text: str) -> str:
    """Remove punctuation from str"""
    # 3rd agrument in make trans -> what is removed.
    # empty arguments 1, 2, mean string stays same,
    translator = str.maketrans('','', string.punctuation)
    return text.translate(translator)

# helper
def _normalize_unicode(text:str)-> str:
    """Normalize special characters to the same format"""
    return unicodedata.normalize("NFKC", text)

# orchestrator
def normalize_value(value):
    """Takes a column and applies normalization steps to all values"""

    normalization_stages = [
        _normalize_unicode,
        _remove_whitespace,
        _to_lower,
        # NOTE: Punctuation intentionally kept for SBERT
    ]
    # internal helper to loop through normalization stages
    def _apply_stages(s: Optional[str]) -> Optional[str]:
        """sequentially apply methods in stages"""
        # incase the list of stages is empty
        if s is None or s=="":
            warnings.warn("No normalization applied: value is None",  stacklevel=2)
            return None
        for stage in normalization_stages:
            s = stage(s)
        return s
    
    # if value is text, apply directly
    if isinstance(value, str):
        return _apply_stages(value)
    # if value is a list of text, iterate through list values
    elif isinstance(value, (list, np.ndarray)):
        return [_apply_stages(v) for v in value if v is not None]
    # if not str, list(str), simply return value
    return value