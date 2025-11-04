# src/ds_utils/text_processing.py
import re
import nltk
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer
from nltk.corpus import stopwords, wordnet
# from nltk.tokenize import word_tokenize
from . import ds_constants as const


lemmatizer = WordNetLemmatizer()
ENGLISH_STOP_WORDS = set(stopwords.words('english'))

def ensure_nltk_assets():
    """
    Checks for and downloads required NLTK data models.
    This function is designed to be called once during setup.
    """
    print("Checking for NLTK assets...")
    required_assets = [
        ('tokenizers/punkt', 'punkt'),
        ('taggers/averaged_perceptron_tagger', 'averaged_perceptron_tagger'),
        ('corpora/wordnet', 'wordnet'),
        ('corpora/stopwords', 'stopwords')
    ]
    
    missing_assets = []
    for path, asset_id in required_assets:
        try:
            nltk.data.find(path)
        except LookupError:
            missing_assets.append(asset_id)
            
    if not missing_assets:
        print("All NLTK assets are already downloaded.")
    else:
        print(f"Downloading missing NLTK assets: {missing_assets}...")
        for asset_id in missing_assets:
            nltk.download(asset_id)
        print("NLTK assets download complete.")

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
def tokenize_text(text: str) -> list:
    """
    Takes a sentence and processes it in the correct order:
    - Converts to lowercase and tokenizes into words.
    - POS tags the words.
    - Lemmatizes each word based on its POS tag.
    - Removes stopwords (except for interrogative keywords).
    - Normalizes specific pronouns (e.g., 'whom' -> 'who').
    
    :param text: The input text to be processed.
    :return: A list of cleaned, lemmatized tokens.
    :rtype: list
    """
    # 1. Tokenize the text
    # Keep only letters and spaces and punctuation -> keeping numbers for numeric answers
    tokens = re.findall(r'\b\w+\b', text.lower())
    
    # 2. POS tag the raw tokens
    pos_tags = pos_tag(tokens)

    # 3. Lemmatize each word based on its tag
    lemmatized_words = [lemmatizer.lemmatize(word, get_wordnet_pos(tag)) for word, tag in pos_tags]
    
    # 4. Remove stopwords from the lemmatized list
    keywords_to_keep = set(const.INTERROGATIVE_KEYWORDS_LIST) | {'yes', 'no'}
    custom_stopwords = ENGLISH_STOP_WORDS - keywords_to_keep
    filtered_tokens = [word for word in lemmatized_words if (word not in custom_stopwords) and (len(word) > 1)]

    # 5. Post-processing step to normalize `who`` pronoun cases
    pronoun_map = {
        'whom': 'who',
        'whose': 'who'
    }
    # Apply the mapping to the lemmatized list
    final_tokens = [pronoun_map.get(word, word) for word in filtered_tokens]
    # ------------------------------------

    return final_tokens
