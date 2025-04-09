# Question handling

class Question:
    """Represents a single trivia question with its answer."""
    
    def __init__(self, question_text: str, correct_answer: str, keywords: list = None):
        """
        Initializes a Question object.

        Args:
            question_text: The text of the trivia question.
            correct_answer: The text of the correct answer.
        """
        if keywords is None:
            keywords = []  # Set an empty list if no keywords are provided
        self.question_text = question_text
        self.correct_answer = correct_answer
        self.keywords = keywords

    def __str__(self):
        return f"Question: {self.question_text},\nAnswer: {self.correct_answer},\nKeywords: {', '.join(self.keywords)}"

    def __repr__(self):
        return f"Question(question_text='{self.question_text}', correct_answer='{self.correct_answer}', keywords={self.keywords})"
    
    def __eq__(self, other):
        if not isinstance(other, Question):
            return NotImplemented
        return (self.question_text == other.question_text and 
                self.correct_answer == other.correct_answer)
                #self.keywords == other.keywords
    
    def provide_question(self):
        """Provides question for game"""
        return f"Question: {self.question_text}"
    
    def provide_answer(self):
        """Provides corresponding answer for the question for the game"""
        return f"Answer: {self.correct_answer}"
    
    def provide_keywords(self):
        """Returns the keywords associated with the question for hints."""
        return f"Keywords: {self.keywords}"
    
    def check_answer(self, player_answer: str):
        """Checks if the player provided answer is correct by comparing it to the correct answer."""
        return player_answer.lower() == self.correct_answer.lower()