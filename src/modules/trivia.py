# Question handling

from dataclasses import dataclass, field
from typing import List # Or Set

  # --- NO NEED TO MANUALLY WRITE __init__, __repr__, __eq__ --- @dataclass generates them automatically using type hints since Q & A are data types"
@dataclass
class Question:
    """Represents a single trivia question with its answer."""
    
    # 1. Define attributes using type hints
    question_id: int 
    question_text: str
    correct_answer: str

    # 2. Using field() for default mutable type
    keywords: List[str] = field(default_factory=list) # Use default_factory for list/set/dict

    def __str__(self):
        return f"Question: {self.question_text},\nAnswer: {self.correct_answer},\nKeywords: {', '.join(self.keywords)}"
  
    def check_answer(self, player_answer: str):
        """Checks if the player provided answer is correct by comparing it to the correct answer."""
        return player_answer.lower() == self.correct_answer.lower()