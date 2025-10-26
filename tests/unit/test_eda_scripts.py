"""
Unit tests for the eda_scripts methods used for dataset processing for the HPtrivia_game.
"""
# pylint: disable=redefined-outer-name, protected-access
import pytest
from ds_utils import eda_scripts as eda
from ds_utils import ds_constants as const

MONTH_NAMES = {
    'january', 'jan', 'february', 'feb', 'march', 'mar', 'april', 'apr',
    'may', 'june', 'jun', 'july', 'jul', 'august', 'aug', 'september', 'sep',
    'october', 'oct', 'november', 'nov', 'december', 'dec'
}
class TestAnswerTypeClassification:
    """Tests for the classify_answer_type function in eda_scripts.py"""
    @pytest.fixture
    def date_strings(self):
        """A fixture that provides a list of date-like strings."""
        
        return ["July 31, 1980", "May 2, 1998", "2025-08-29", "23 March", "1 Jan 25", "1-13-90"]

    @pytest.fixture
    def year_strings(self):
        """A fixture that provides a list of year-like strings."""
        return ["1994", "2001", "1108 AD", "65 BC", "21st century", "5th century"]

    @pytest.fixture
    def numeric_strings(self):
        """A fixture that provides a list of numeric strings."""
        return ["42", "3.14", "700."]

    @pytest.fixture
    def text_strings(self):
        """A fixture that provides a list of purely textual strings."""
        return ["The one-eyed witch", "Clause Three", "Gryffindor", "Nimbus 2000", "Warlock's Convention of 1709", "700 galleons"]

    @pytest.fixture
    def answer_test_cases(self):
        """Provides a list of test cases, each with a mock row and its expected type."""
        return [
            {'row': {'answer': "The one-eyed witch", 'is_numeric_answer': False}, 'expected': 'text'},
            {'row': {'answer': "Greenhouse One", 'is_numeric_answer': False}, 'expected': 'text'},
            {'row': {'answer': "14 sickles.", 'is_numeric_answer': False }, 'expected': 'text'},
            {'row': {'answer': "July 30", 'is_numeric_answer': False}, 'expected': 'date'},
            {'row': {'answer': "Page 394 (the page on werewolves)", 'is_numeric_answer': False}, 'expected': 'text'},
            {'row': {'answer': "12 Grimmauld Place", 'is_numeric_answer': False}, 'expected': 'text'},
            {'row': {'answer': "1050 AD", 'is_numeric_answer': False}, 'expected': 'year'},
            {'row': {'answer': "13", 'is_numeric_answer': True}, 'expected': 'numeric'},
            {'row': {'answer': "115 years old", 'is_numeric_answer': False}, 'expected': 'text'},
            {'row': {'answer': "2: the diary and the ring", 'is_numeric_answer': False}, 'expected': 'text'}
        ]

    def test_classify_answer_type_with_dates(self, date_strings):
        """Tests that all strings in the date_strings fixture are classified as 'date'."""
        for i, answer in enumerate(date_strings):
            mock_row = {'answer': answer}
            result = eda.classify_answer_type(mock_row)
            assert result == 'date', f"Failed at index {i}: '{answer}'. Got '{result}', expected 'date'."
            
    def test_classify_answer_type_with_years(self, year_strings):
        """Tests that all strings in the year_strings fixture are classified as 'year'."""
        for i, answer in enumerate(year_strings):
            mock_row = {'answer': answer}
            result = eda.classify_answer_type(mock_row)
            assert result == 'year', f"Failed at index {i}: '{answer}'. Got '{result}', expected 'year'."

    def test_classify_answer_type_with_numerics(self, numeric_strings):
        """Tests that all strings in the numeric_strings fixture are classified as 'numeric'."""
        for i, answer in enumerate(numeric_strings):
            mock_row = {'answer': answer, 'is_numeric_answer': True}
            result = eda.classify_answer_type(mock_row)
            assert result == 'numeric', f"Failed at index {i}: '{answer}'. Got '{result}', expected 'numeric'."

    def test_classify_answer_type_with_text(self, text_strings):
        """Tests that all strings in the text_strings fixture are classified as 'text'."""
        for i, answer in enumerate(text_strings):
            mock_row = {'answer': answer}
            result = eda.classify_answer_type(mock_row)
            assert result == 'text', f"Failed at index {i}: '{answer}'. Got '{result}', expected 'text'."

    def test_classify_answer_type_with_test_cases(self, answer_test_cases):
        """Tests the classify_answer_type function against a list of diverse test cases."""
        for i, case in enumerate(answer_test_cases):
            input_row = case['row']
            expected_type = case['expected']
            result = eda.classify_answer_type(input_row)
            assert result == expected_type, \
                f"Failed at case {i} on answer '{input_row['answer']}'. Got '{result}', expected '{expected_type}'."

class TestQuestionCategorization:
    """"""
    
    @pytest.fixture
    def multiple_choice_strings(self):
        """A fixture that provides a list of multiple choice question strings."""
        return [
            "Which of the following is NOT a form of Transfiguration: Switching, Vanishing, Enchantment, Conjuration.",
            "Who is NOT in Slytherin: Lavender Brown, Pansy Parkinson, Blaise Zabini, or Gregory Goyle?",
            "Who among the following served as a Hufflepuff Prefect: Justin Finch-Fletchley, Zacharias Smith, Ernie Macmillan, or Anthony Goldstein?",
            "In the first Transfiguration lesson, what does Professor McGonagall transform her desk into as a demonstration: a badger, an owl, a pig, or a baboon?",
            "What flavour does Dumbledore get when trying a Bertie Bott’s Every Flavour Bean in Philosopher’s Stone: Liver, Vomit, Earwax, or Booger?",
            "How many O.W.L. (Ordinary Wizarding Level) exams did Harry Potter pass: 5, 7, 9, or 10?",
            "An Infusion of Wormwood is NOT an ingredient in which of these potions: Draught of Living Death, Elixir to Induce Euphoria, Beautification Potion, or Draught of Peace?",
            "Bouncing Bulbs are notoriously difficult for which of these Herbology actions: Watering, Pruning, Potting, or Fertilizing?"
        ]
        
        
    
    def test_categorize_question_when_mcq(self, multiple_choice_strings):
        """Tests that all strings in the multiple_choice_strings fixture are categorized as 'MCQ'."""
        for i, question_text in enumerate(multiple_choice_strings):
            # Step 1: Simulate your pipeline to get the actual main_keyword
            # This makes the test realistic.
            tokens = question_text.lower().split() # A simple tokenizer for the test
            keywords_found = [word for word in tokens if word in const.INTERROGATIVE_KEYWORDS_LIST]
            main_kw = eda.get_main_keyword(keywords_found)

            # Step 2: Create the mock row with the real main_keyword
            mock_row = {'question': question_text, 'main_keyword': main_kw}

            # Step 3: Run the test
            result = eda.categorize_question(mock_row)
            assert result == 'MCQ', f"Failed at index {i}: '{question_text}'. Got '{result}', expected 'MCQ'."

        