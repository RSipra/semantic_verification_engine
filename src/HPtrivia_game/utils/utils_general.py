"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

Utility functions for common methods across modules

"""
import string

def clean_input_string(raw_input: str) -> str:
    """
    Cleans a string by stripping whitespace, removing punctuation,
    and converting to lowercase.
    """
    # validate
    if not isinstance(raw_input, str):
        return ""
    translator = str.maketrans('', '', string.punctuation)
    return raw_input.lower().translate(translator).strip()
        
    