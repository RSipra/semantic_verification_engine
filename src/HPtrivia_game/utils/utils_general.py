"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

Utility functions for common methods across modules

"""
import string

def clean_input_string(raw_input: str) -> str:
    """
    Cleans a string by stripping whitespace, removing punctuation 
    (including smart quotes), and converting to lowercase.
    """
    # validate
    if not isinstance(raw_input, str):
        return ""

    # Define extra characters that string.punctuation misses
    smart_quotes = "‘’“”"

    # Create a translator that removes BOTH standard AND smart punctuation
    translator = str.maketrans('', '', string.punctuation + smart_quotes)

    return raw_input.lower().translate(translator).strip()
    