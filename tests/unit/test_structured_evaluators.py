"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for structured (rule-based) evaluators
-----------------------------------------------------------------------

These tests validate the expected runtime behavior of deterministic
evaluators responsible for structured answer types such as numeric,
year, and date-based responses.

Test coverage includes:
    - Successful exact-match evaluation paths
    - Input normalization behavior
    - Invalid and missing input handling
    - Domain-specific edge cases and ambiguity rejection
    - Resolution tier consistency

The purpose of this suite is to preserve evaluator behavior during
runtime refactoring and future development iterations.

Notes:
    - These tests verify evaluator contracts, not exploratory logic design
    - Structured evaluators are intentionally strict and deterministic
    - Semantic similarity evaluators are tested separately
    
"""

from engine.evaluators import structured_evaluators as sv
from core.constants import AnswerType

## 1: Numeric answers (number, year)

## 1.1: numeric answers
# happy path (correct evaluation) - numeric
def test_numeric_evaluator_with_correct_num():
    """Valid numeric answer should be evaluated successfully."""
    # arrange
    player_answer = 7
    gold_answer = str(7)
    answer_type = AnswerType.NUMERIC
    
    # act
    result = sv._check_numeric_answer(player_answer,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'numeric_exact_pass'

# happy path (correct evaluation) - number as words
def test_numeric_evaluator_with_correct_num_as_word():
    """Valid numeric answer written as words should be evaluated successfully."""
    # arrange
    player_answer = "seventy five"
    gold_answer = str(75)
    answer_type = AnswerType.NUMERIC
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'numeric_exact_pass'
    
# invalid path - no player answer
def test_numeric_evaluator_no_player_answer():
    """
    Missing player answer should fail
    """
    # arrange
    player_answer = ""
    gold_answer = str(75)
    answer_type = AnswerType.NUMERIC
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail_invalid_or_no_num'

# invalid path - no gold answer
def test_numeric_evaluator_no_gold_answer():
    """
    Missing player answer should fail
    """
    # arrange
    player_answer = "75"
    gold_answer = ""
    answer_type = AnswerType.NUMERIC
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail_invalid_gold'         

# invalid path - number represented incorrectly as words
def test_numeric_evaluator_with_incorrect_num_as_word():
    """
    invalid numeric answer written as words should fail. 
    This will be resolved as 7 5 instead of 75
    """
    # arrange
    player_answer = "seven five"
    gold_answer = str(75)
    answer_type = AnswerType.NUMERIC
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail'          

## 1.2: Year type answers

# happy path (correct evaluation) - year
def test_numeric_evaluator_with_correct_year():
    """Valid year answer should be evaluated successfully."""
    # arrange
    player_answer = 1990
    gold_answer = str(1990)
    answer_type = AnswerType.YEAR
    
    # act
    result = sv._check_numeric_answer(player_answer,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'numeric_exact_pass'
    
# happy path (correct evaluation) - year
def test_numeric_evaluator_with_correct_bc_year():
    """Valid BCE year answer should be evaluated successfully."""
    # arrange
    player_answer = "200 BC"
    gold_answer = "200 BC"
    answer_type = AnswerType.YEAR
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'numeric_exact_pass'
    
# happy path (correct evaluation) - year
def test_numeric_evaluator_with_correct_ad_year():
    """Valid AD year answer should be evaluated successfully."""
    # arrange
    player_answer = "200 AD"
    gold_answer = "200 AD"
    answer_type = AnswerType.YEAR
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'numeric_exact_pass'

# invalid path - no player answer 
def test_numeric_evaluator_with_no_player_year():
    """Missing player answer for year should fail"""
    # arrange
    player_answer = ""
    gold_answer = str(1990)
    answer_type = AnswerType.YEAR
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail_invalid_or_no_num'

# invalid path - no gold answer
def test_numeric_evaluator_with_no_gold_year():
    """Missing gold year answer should fail"""
    # arrange
    player_answer = str(1990)
    gold_answer = ""
    answer_type = AnswerType.YEAR
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail_invalid_gold'    

# invalid path - answer is not a year
def test_numeric_evaluator_with_incorrect_year_text():
    """invalid year answer should fail"""
    # arrange
    player_answer = "i dont know"
    gold_answer = str(1990)
    answer_type = AnswerType.YEAR
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail_invalid_or_no_num'

# invalid path - year
def test_numeric_evaluator_with_impossible_year():
    """invalid year answer should fail"""
    # arrange
    player_answer = "The year 6570"
    gold_answer = str(1990)
    answer_type = AnswerType.YEAR
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail'

# edge case - shorthand year fail
def test_numeric_evaluator_with_shorthand_year():
    """shorthand year answer should be failed. Too ambiguous especially for tracer."""
    # arrange
    player_answer = "'90"
    gold_answer = "1990"
    answer_type = AnswerType.YEAR
    
    # act
    processed_player_ans = sv._preprocess_numeric_player_ans(player_answer, answer_type)
    result = sv._check_numeric_answer(processed_player_ans,answer_type, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'numeric_exact_fail'
 

## 2: Date-format answers

# happy path (correct evaluation) - date
def test_date_evaluator_with_correct_value():
    """Valid date answer should be evaluated successfully."""
    # arrange
    player_answer = "31 July 1980"
    gold_answer = "31 July 1980"
    
    # act
    normalized_date = sv._normalize_date_text(player_answer)
    date_entities = sv._extract_date_entities(normalized_date)
    result = sv._check_date_answer(date_entities, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'date_exact_pass'  

# invalid path: player answer missing
def test_date_evaluator_no_player_ans():
    """No player date answer should be failed"""
    # arrange
    player_answer = ""
    gold_answer = "31 July 1980"
    
    # act
    normalized_date = sv._normalize_date_text(player_answer)
    date_entities = sv._extract_date_entities(normalized_date)
    result = sv._check_date_answer(date_entities, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'date_exact_fail_invalid_player_ans'
    
# invalid path: gold answer missing
def test_date_evaluator_no_gold_ans():
    """Missing gold answer should fail"""
    # arrange
    player_answer = "31 July 1980"
    gold_answer = ""
    
    # act
    normalized_date = sv._normalize_date_text(player_answer)
    date_entities = sv._extract_date_entities(normalized_date)
    result = sv._check_date_answer(date_entities, gold_answer)
    
    # assert
    assert result.is_correct is False
    assert result.resolution_tier == 'date_exact_fail_invalid_gold'

# edge case: numerical dates with backslashes
def test_date_evaluator_with_backslashes():
    """The numeric formatted date should pass"""
    # arrange
    player_answer = "31/7/1980"
    gold_answer = "31 July 1980"
    
    # act
    normalized_date = sv._normalize_date_text(player_answer)
    date_entities = sv._extract_date_entities(normalized_date)
    result = sv._check_date_answer(date_entities, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'date_exact_pass' 

# edge case: alternate word representation
def test_date_evaluator_with_month_first():
    """The numeric formatted date should pass"""
    # arrange
    player_answer = "July 31rst, 1980"
    gold_answer = "31 July 1980"
    
    # act
    normalized_date = sv._normalize_date_text(player_answer)
    date_entities = sv._extract_date_entities(normalized_date)
    result = sv._check_date_answer(date_entities, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'date_exact_pass'       
    
# edge case: american format
def test_date_evaluator_with_american_format():
    """The american format date should pass"""
    # arrange
    player_answer = "07-31-80"
    gold_answer = "31 July 1980"
    
    # act
    normalized_date = sv._normalize_date_text(player_answer)
    date_entities = sv._extract_date_entities(normalized_date)
    result = sv._check_date_answer(date_entities, gold_answer)
    
    # assert
    assert result.is_correct is True
    assert result.resolution_tier == 'date_exact_pass'  
          