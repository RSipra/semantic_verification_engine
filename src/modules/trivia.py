''' 
TRIVIA MODULE

This module is part of the Trivia game application. It is responsible for loading questions, 
checking answers, and display the question and answer.

Overview:
* Trivia class: loads and manages a set of trivia questions and answers randomly selected from 
the dataset.
* Question class: represents a single trivia question and its answer. The class includes methods 
for checking the correctness of an answer and for displaying the question and answer.
  
  '''
# Import necessary libraries:
from dataclasses import dataclass, field
from typing import List
# import random

class Trivia:
    """Represents the random set of questions loaded from the dataset for the Trivia game session."""
    
    # Number of questions to load (can be user defined variable later as pre-set list of options ,e.g. 10, 20, 30)
    NUM_QUESTIONS = 10
    
    def __init__(self):
        """Initialize the Trivia session with an empty list of questions."""
        self.questions = []  # List to store questions

       
    # --- NEXT STEP: How do I load the 20 questions? ---
    # Option 1: Load during __init__
    # def __init__(self, all_questions_data: list): # Pass in the full dataset
    #     self.questions: List[Question] = self._load_random_questions(all_questions_data)
    
    # Option 2: Load via a separate method
    # def load_game_questions(self, all_questions_data: list):
    #     self.questions = self._load_random_questions(all_questions_data)

    # Helper method (could be private)
    # def _load_random_questions(self, all_questions_data: list) -> List[Question]:
    #    # 1. Ensure you have enough questions in the source data
    #    # 2. Use random.sample() to pick NUM_QUESTIONS unique items
    #    # 3. Convert the selected raw data items into Question objects
    #    # 4. Return the list of Question objects
    #    pass # Implement this logic

# --- NO NEED TO MANUALLY WRITE __init__, __repr__ --- @dataclass generates them automatically using 
# type hints since Q & A are data types but choosing to override __eq__ to compare objects so 
# keywords are excluded for now.

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
    