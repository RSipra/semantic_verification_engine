"""
Unit tests for the Question class and its methods in the HPtrivia_game package.
"""
from dataclasses import FrozenInstanceError
import pytest
from HPtrivia_game.trivia_manager import Question
# pylint: disable=redefined-outer-name

@pytest.fixture
def sample_question():
    """Provides a standard Question instance for testing."""
    return Question(
        question_id=214,
        question_text = "What was the name of Neville Longbottom's pet toad?",
        correct_answer="Trevor",
        interrogative_keyword=['what'],
        question_keywords=['what', 'name', 'Neville', 'Longbottom', 'pet', 'toad'],  
        answer_keywords=['Trevor'],  
        session_id= 5 
        )  

def test_question_initialization(sample_question: Question):
    """Tests that the dataclass correctly initializes attributes."""
    assert sample_question.session_id == 5
    assert sample_question.question_id == 214
    assert sample_question.question_text == "What was the name of Neville Longbottom's pet toad?"
    assert sample_question.correct_answer == "Trevor"

def test_question_equal_full(sample_question: Question):
    """Test the equality of two Question instances."""
    question1 = sample_question
    question2 = Question(
        question_id=214,
        question_text = "What was the name of Neville Longbottom's pet toad?",
        correct_answer="Trevor",
        interrogative_keyword=['what'],
        question_keywords=['what', 'name', 'Neville', 'Longbottom', 'pet', 'toad'],  
        answer_keywords=['Trevor'],  
        session_id= 5 
    )
    assert question1 == question2

def test_question_equal_main_parameters_same_only(sample_question: Question):
    """Test the equality of two Question instances when onlyl the required arguments are equal."""
    question1 = sample_question
    question2 = Question(
        question_id=214,
        question_text = "What was the name of Neville Longbottom's pet toad?",
        correct_answer="Trevor",
        interrogative_keyword=['why'],
        question_keywords=['what', 'name'],  
        answer_keywords=['Taylor'],  
        session_id= 25
    )
    assert question1 == question2
    
def test_question_equal_when_not_same(sample_question: Question):
    """Test the equality of two Question instances."""
    question1 = sample_question
    question2 = Question(
        question_id=204,
        question_text = "What was the name of Neville Longbottom's pet toad?",
        correct_answer="Trevor",
        interrogative_keyword=['what'],
        question_keywords=['what', 'name', 'Neville', 'Longbottom', 'pet', 'toad'],  
        answer_keywords=['Trevor'],  
        session_id= 5 
    )
    assert question1 != question2
    
def test_question_str(sample_question: Question):
    """Tests the string representation of the Question object."""
    expected = f"[Session #{sample_question.session_id}] QID {sample_question.question_id}: {sample_question.question_text}\nAnswer: {sample_question.correct_answer}" 
    assert str(sample_question) == expected
    
def test_question_is_immutable(sample_question: Question):
    """Tests that attributes cannot be changed after creation (frozen=True)."""
    # This 'with' block tells pytest: "I EXPECT the code inside here to raise this specific error."
    # The test PASSES if the error is raised. It FAILS if no error is raised.
    with pytest.raises(FrozenInstanceError):
        sample_question.correct_answer = "Scabbers"  # pyright: ignore[reportAttributeAccessIssue]
    
def test_question_check_answer(sample_question):
    """Tests the check_answer method for correct answers."""
    # checking correct answers
    assert sample_question.check_answer("Trevor") is True
    assert sample_question.check_answer("trevor") is True  # Case-insensitive check
    assert sample_question.check_answer("  Trevor  ") is True  # Handles whitespac
    # checking incorrect answers
    assert sample_question.check_answer("Harry") is False  # Incorrect answer
    assert sample_question.check_answer("") is False  # Empty answer
    assert sample_question.check_answer("  ") is False  # Only whitespace answer
    assert sample_question.check_answer("Trever") is False  # spelling mistake
    