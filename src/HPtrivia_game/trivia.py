'''
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

CLI MVP (core logic) -> trivia module (data)

------------------------------------------------------------------

This module manages the core trivia game functionality, including:
- Loading and storing trivia questions
- Handling question presentation and answer validation
- Scoring logic and question progression

Classes:
    - Trivia (load session trivia questions)
    - Question (responsible for individual question and answer logic)

Functions:
    - load_questions(): Loads questions from file or data source
    - shuffle_questions(): Randomizes the order of questions
    - validate_answer(): Checks if a player's answer is correct

This module is typically used by the GameController during gameplay.
  
  '''
# Import necessary libraries:
from dataclasses import dataclass, field
from typing import List
import pandas as pd
from HPtrivia_game.constants import NUM_QUESTIONS_PER_SESSION

class Trivia:
    """
    The dataset / questions manager
    Represents the random set of questions loaded from the dataset for the Trivia game session.
    """
  
    def _load_dataset(self, csv_filepath: str):
        # return dataframe of full dataset
        df = pd.read_csv(csv_filepath, index_col=False)
        return df
    
    @staticmethod
    def _load_questions(df):
        # select n random questions from the loaded dataframe:
        session_df = df.sample(
            n = NUM_QUESTIONS_PER_SESSION,
            random_state = 26,
            axis = 0,
            replace = False
        )
        # convert session questions from df to dict for easy access.
        session_questions_dict = session_df.to_dict()
        return session_questions_dict
    
    def start(self, csv_filepaht):
        pass

    def __init__(self,selected_questions_dict: dict):
        self.questions = selected_questions_dict

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
    
    def _prepare_question_to_ask(self):
        # Prepare the question for View class to ask player
        pass
  
    def _check_answer(self, player_answer: str):
        """
        Checks if the player provided answer is correct by comparing it to the correct answer.
        """
        return player_answer.lower() == self.correct_answer.lower()
    