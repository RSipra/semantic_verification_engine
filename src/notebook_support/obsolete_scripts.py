# src/ds_utils/OBSOLETE_SCRIPTS.py
import re
import numpy as np
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords, wordnet
# from nltk.tokenize import word_tokenize
from . import ds_constants as const


lemmatizer = WordNetLemmatizer()
ENGLISH_STOP_WORDS = set(stopwords.words('english'))
FACTUAL_RECALL_KEYWORDS = ['what', 'name', 'who', 'where', 'when']

# Function to convert POS tags for better lemmatization
def get_wordnet_pos(nltk_tag:str) -> str:
    """
    Map an NLTK part-of-speech (POS) tag to the corresponding WordNet POS tag.
    This function helps improve lemmatization by converting POS tags generated 
    by NLTK's `pos_tag` into the format expected by WordNet's lemmatizer. 
    If the tag does not match any known category, it defaults to `NOUN`.
    
    :param nltk_tag: The POS tag from NLTK's `pos_tag` function (e.g., 'NN', 'VB', 'JJ', 'RB').
    :return: The corresponding WordNet POS tag (e.g., `wordnet.NOUN`, `wordnet.VERB`, etc.).
    :rtype: str
    """
    if nltk_tag.startswith('J'):
        return wordnet.ADJ
    elif nltk_tag.startswith('V'):
        return wordnet.VERB
    elif nltk_tag.startswith('N'):
        return wordnet.NOUN
    elif nltk_tag.startswith('R'):
        return wordnet.ADV
    else:
        return wordnet.NOUN  # Default to noun

# Custom tokenizer with lemmatization
def tokenize_text_v0_obsolete(text: str) -> list:
    """
    Takes a sentence:
    - Removes punctuation
    - Converts to lowercase
    - Tokenizes into words and numbers
    - Removes stopwords except for interrogative keywords
    - POS tags the words
    - Lemmatizes each word based on POS tagging
    
    :param text: The input text to be processed.
    :return: A list of lemmatized tokens.
    :rtype: list
    """
    
    # Keep only letters and spaces and punctuation -> keeping numbers for numeric answers
    # text = re.sub(r'[^a-zA-Z0-9\s]', '', text).lower()  # removes punctuation, keeps numbers, converts to lowercase
    # tokens = word_tokenize(text)
    tokens = re.findall(r'\b\w+\b', text.lower())
    
    # Remove stopwords and single letter words before POS tagging for efficiency.
    # Exclude words from the stop words list that can help understand the questions in EDA
    
    custom_stopwords = ENGLISH_STOP_WORDS - set(const.INTERROGATIVE_KEYWORDS_LIST)
    filtered_tokens = [word for word in tokens if (word not in custom_stopwords) and (len(word) > 1)]

    # POS tagging
    pos_tags = pos_tag(filtered_tokens)

    # Lemmatize each word
    lemmatized_words = [lemmatizer.lemmatize(word, get_wordnet_pos(tag)) for word, tag in pos_tags]

    return lemmatized_words

def get_main_keyword_v0_obsolete(tag_list: list[str]) -> str:
    """
    Extracts the first keyword from a list to serve as the main keyword.

    This was the initial, simplistic approach. It assumes the first token
    in the list of identified keywords is the most important one. It does not
    use any priority system.

    If the input list is empty, it assigns the category 'unassigned'.

    :param tag_list: A list of keyword strings.
    :type tag_list: list[str]
    :return: The first keyword from the list or 'unassigned'.
    :rtype: str
    """
    if isinstance(tag_list, (list, np.ndarray)):  # because using apply() can return np.ndarray
        if len(tag_list) > 0:
            return tag_list[0]
        else:
            return 'unassigned'

    return 'other'  # fallback for unexpected types 
