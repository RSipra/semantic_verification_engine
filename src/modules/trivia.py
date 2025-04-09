''' QUESTION AND ANSWER CLASS
    This module contains the Question class, which represents a trivia question and its answer.
    The class includes methods for checking the correctness of an answer and for displaying the question and answer.'''

from dataclasses import dataclass, field
from typing import List

# --- NO NEED TO MANUALLY WRITE __init__, __repr__ --- @dataclass generates them automatically using type hints since Q & A are data types"
# but choosing to override __eq__ to compare objects so keywords are excluded for now.

@dataclass(eq=False)
class Question:
    """Represents a single trivia question with its answer."""
    
    # 1. Define attributes using type hints
    question_id: int 
    question_text: str
    correct_answer: str

    # 2. Using field() for default mutable type
    keywords: List[str] = field(default_factory=list) # Use default_factory for list/set/dict

    def __eq__(self, other):
        """Overrides @dataclass equality operator to compare question_id, question_text, and correct_answer to identify if question
        and answer are identical."""
        if isinstance(other, Question):
            return self.question_id == other.question_id and \
                   self.question_text == other.question_text and  \
                   self.correct_answer == other.correct_answer
        return NotImplemented
    
    def __str__(self):
        return f"Question: {self.question_text},\nAnswer: {self.correct_answer},\nKeywords: {', '.join(self.keywords)}"
  
    def check_answer(self, player_answer: str):
        """Checks if the player provided answer is correct by comparing it to the correct answer."""
        return player_answer.lower() == self.correct_answer.lower()
    