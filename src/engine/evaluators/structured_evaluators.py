
"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP (Tracer Build) ->  Structured (rule-based) Evaluators 
                          (routed by numeric, year, date type answers )
-----------------------------------------------------------------------

This module implements deterministic evaluation logic for structured
answer types. It provides fast, rule-based resolution for answers that can be
evaluated without semantic similarity models.

Evaluation flow:
    1. Input preprocessing (numeric/date normalization)
    2. Deterministic comparison against gold answers
    3. Structured result emitted via BaseEvalResults DTO

Supported evaluation types:
    - Numeric answers (integers, years, word-to-number parsing)
    - Date answers (day/month/year extraction with normalization)

Design principles:
    - Fully deterministic (no embeddings or LLMs)
    - Fail-safe parsing with explicit fallback tiers
    - Strict comparison logic after normalization
    - Produces standardized evaluation DTOs for downstream aggregation

Notes:
    - This module represents the "exact match / rule-based" evaluation layer
    - Semantic similarity evaluators operate in a separate pipeline stage
    - TODO: Date parsing currently relies on heuristic extraction using `search_dates`.
      This layer should be revisited for robustness and ambiguity handling
      during future runtime development.

"""
import re
from datetime import datetime
from dateparser.search import search_dates
from word2number import w2n
from core.constants import AnswerType
from engine.dto import BaseEvalResults
from engine.evaluators.constants import HOLIDAY_MAP

## 1: Numeric answers (number, year)

def _check_for_bc_indicator(answer:str):
    """Check if answer explicitly indicates BC/BCE date."""
    pattern = r'\b(bc|bce|b\.c\.|b\.c\.e\.)\b'
    return bool(re.search(pattern, answer.lower()))

def _normalize_numeric_text(raw_answer:str):
    """
    Shared helper to clean and translate numeric or year strings 
    for both player answers and gold dataset answers.
    """
    # 1. base string cleanup
    clean_text = str(raw_answer).lower().strip().replace(",", "")
    
    # 2. clamp floating minus signs (turns "- 1718" into "-1718")
    clean_text = re.sub(r'-\s+', '-', clean_text)
    
    return clean_text

def preprocess_numeric_player_ans(raw_player_ans:str,
                                   answer_type:AnswerType, 
                                   hard_cap:int = 1):
    """
    Sanitizes raw player text into a single integer.
    Enforces an anti-hedging hard cap of 1.
    Returns None if hedging is detected or no valid number is found.
    """
    # 1. normalize answer (strip white space, any 1000 comma separater)
    ans_text = _normalize_numeric_text(raw_player_ans)
    
    # 2. check if year in gold_answer has BC or BCE,
    is_bc = False
    if answer_type==AnswerType.YEAR:
        is_bc = _check_for_bc_indicator(ans_text)
        
    # 2. extract numbers from surrounding text -> e.g. "he was 32 years old" -> 32
    matches = re.findall(r'(?<!\w)-?\b\d+\b', ans_text)
    
    # 3. check for hedging (ans: "32 or 33") and if BC if the answer is year 
    if len(matches) == 1:
        # if the year is BC or BCE:
        num = int(matches[0])
        # add indicator that it is BC year by making negative
        return -1 * abs(num) if is_bc else num

    if len(matches) > hard_cap:
        return None 

    # 5. check if the answer is written out in words using w2n
    if not matches:    
        try:
            num = int(w2n.word_to_num(ans_text))
            # check if bc year check applies 
            return num * -1 if is_bc else num
        except (ValueError, TypeError):
            return None

def check_numeric_answer(player_answer_num: int | None,
                          answer_type: AnswerType,
                          gold_answer: str) -> BaseEvalResults:
    """
    Evaluates a numeric Free Response question by comparing a preprocessed 
    player integer against the extracted integer of the gold answer.
    
    Notes:
        - Relies on an upstream preprocessor to convert player text into a single `int` or `None`.
        - TODO (Phase 2): Upgrade to `float` and `math.isclose()` instead of `int` to 
          safely handle decimal answers and prevent backend crashes during casting
          for answers such as "platform 9 3/4".
          
    Args:
        player_answer_num (int | None): The parsed numeric value from the player's input.
        gold_answer (str): The raw string of the correct answer (e.g. "150" or "150 points").
        
    Returns:
        BaseEvalResults: A standardized dataclass containing the boolean result 
        and the specific resolution tier.
    """
    result = BaseEvalResults()
    
    # 1. process gold answer
    correct_answer = preprocess_numeric_player_ans(gold_answer, answer_type=answer_type)
    
    if correct_answer is None:
        # failsafe: Prevent an IndexError if gold_answer contains no digits
        result.is_correct = False
        result.resolution_tier = 'numeric_exact_fail_invalid_gold'
        return result
    
    # 2. if the player answer did not have any numbers
    if player_answer_num is None:
        result.is_correct = False
        result.resolution_tier = 'numeric_exact_fail_invalid_or_no_num'
        return result
    
    # 3. check if the correct number is provided
    if player_answer_num == correct_answer:
        result.is_correct = True
        result.resolution_tier = 'numeric_exact_pass'
        return result
    
    # 4. catch all fail
    result.is_correct = False
    result.resolution_tier = 'numeric_exact_fail'
    return result
    
## 2: Date-format answers

def normalize_date_text(raw_text: str) -> str:
    """
    Shared helper to clean and translate raw chronological strings 
    for both player answers and gold dataset answers.
    """
    text = str(raw_text).lower().strip()
    
    # Strip parenthetical hedges (e.g., "halloween (or october 31st)")
    text = re.sub(r'\(.*?\)', '', text)
    # Strips ordinals (st, nd, rd, th, rst) that are attached to numbers
    # Turns "31rst" -> "31", "22nd" -> "22"
    text = re.sub(r'(?<=\d)(st|nd|rd|th|rst)\b', '', text)
    
    # Holiday translation pass
    for holiday, date_str in HOLIDAY_MAP.items():
        if holiday in text:
            text = text.replace(holiday, date_str)
            
    return text

def extract_date_entities(date_string: str) -> dict | None:
    """
    Parses a raw string into Day, Month, and Year entities.
    Accurately detects missing years and assigns them None.
    Returns None if the string isn't a valid date.
    AI written (Gemini)
    """
    # 1. Clean the text (Assumes you added the ordinal regex patch from earlier)
    clean_text = normalize_date_text(date_string)
    
    base_1 = datetime(1900, 1, 1)
    base_2 = datetime(2000, 12, 31)
    
    # 2. Use search_dates to pluck the date out of conversational fluff
    search_1 = search_dates(clean_text, settings={'RELATIVE_BASE': base_1, 'PREFER_DAY_OF_MONTH': 'first'})
    search_2 = search_dates(clean_text, settings={'RELATIVE_BASE': base_2, 'PREFER_DAY_OF_MONTH': 'first'})
    
    # Failsafe: If no dates are found in the text at all
    if not search_1 or not search_2:
        return None
        
    # 3. Extract the first date found in the string
    parse_1 = search_1[0][1]
    parse_2 = search_2[0][1]
    matched_text = search_1[0][0] # The exact substring the parser thinks is a date
    
    # 4. System Year Hallucination Failsafe
    is_hallucinated_year = parse_1.year != parse_2.year
    current_year = datetime.now().year
    
    if parse_1.year == current_year and not is_hallucinated_year:
        year_str = str(current_year)
        short_year = year_str[-2:]
        
        # Did they actually type '2026' or '26' in the matched substring?
        if year_str not in matched_text:
            short_year_count = matched_text.count(short_year)
            day_matches_short = (parse_1.day == int(short_year))
            if short_year_count <= (1 if day_matches_short else 0):
                is_hallucinated_year = True

    # 5. Build and return the hallucination-proof dictionary
    entities: dict[str, int | None] = {
        'day': parse_1.day if parse_1.day == parse_2.day else None,
        'month': parse_1.month if parse_1.month == parse_2.month else None,
        'year': None if is_hallucinated_year else parse_1.year
    }
    
    return entities
            
def check_date_answer(player_entities: dict[str, int | None] | None, gold_answer: str)->BaseEvalResults:
    """
    Evaluates a date-type player answers by comparing preprocessed 
    player dates against the parsed gold answer date.
    """    
    result = BaseEvalResults()
    
    # 1. process gold answer (convert into standard python datetime)
    clean_gold = normalize_date_text(gold_answer)
    gold_entities = extract_date_entities(clean_gold)
    
    if not gold_entities:
        # failsafe: Prevent an IndexError if gold_answer contains no dates
        result.is_correct = False
        result.resolution_tier = 'date_exact_fail_invalid_gold'
        return result
    
    # 2. check if player didn't provide dates
    if player_entities is None:
        result.is_correct = False
        result.resolution_tier = 'date_exact_fail_invalid_player_ans'
        return result
    
    # 3. check if the correct date is provided
    if player_entities == gold_entities:
        result.is_correct = True
        result.resolution_tier = 'date_exact_pass'
        return result
    
    # 4. catch all fail
    result.is_correct = False
    result.resolution_tier = 'date_exact_fail'
    return result
