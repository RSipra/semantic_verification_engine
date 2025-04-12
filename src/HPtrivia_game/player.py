'''
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

CLI MVP (core logic) -> player module (model)

------------------------------------------------------------------
'''

class Player:
    ''' This class represents a player in a game session.'''
    
    def __init__(self, name: str, hogwarts_house: str):
        
        """Initialize the Player with a name and Hogwarts house."""
        # where is the best place to validate? i shoud check at input instead of initialization.
        # Validate the name
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Player name must be a non-empty string.")
        
        # Validate the Hogwarts house
        if not isinstance(hogwarts_house, str) or not hogwarts_house.strip():
            raise ValueError("Hogwarts house must be a non-empty string.")
        valid_houses = ["Gryffindor", "Hufflepuff", "Ravenclaw", "Slytherin"]
        
        if hogwarts_house not in valid_houses:
            raise ValueError(f"Invalid house '{hogwarts_house}'. Valid houses are {valid_houses}.")
        
        # Initialize player attributes
        self._name = name.strip().title()
        self._hogwarts_house = hogwarts_house.strip().capitalize()
        # Initialize score to 0
        self._score = 0
        # Initialize chances left to 3 - can adjust this later
        self._chances_left = 3

    def __str__(self):
        return f"Player '{self._name}' is a member of {self._hogwarts_house} \
            with a current score of {self._score}."

    def __repr__(self):
        return f"Player({self._name}, {self._hogwarts_house}, {self._score})"
    
    def __eq__(self, other):
        '''Check if the other object is an instance of Player'''
        if isinstance(other, Player):
            return self._name == other._name and \
                   self._hogwarts_house == other._hogwarts_house
        return NotImplemented
        # can consider player_id as unique identifier for player later on. 
    
    # getter functions
    @property
    def score(self):
        """Return the player's score"""
        return self._score
    
    @property
    def name(self):
        """Return the player's name"""
        return self._name
    
    @property
    def house(self):
        """Return the player's hogwarts house"""
        return self._hogwarts_house
    
    def add_score(self):
        '''Increase the player's score by 1 point'''
        self._score += 1
        return self._score
    
    def reset_score(self):
        '''Return the player's score back to 0'''
        self._score = 0
        return self._score
    
    def lose_chance(self):
        '''Reduce the player's chances by 1'''
        if self._chances_left <= 0:
            raise ValueError("No chances left.")
        self._chances_left -= 1
        return self._chances_left
    
    def find_player_level(self, total_questions: int):
        '''Return the player's level based on their score at the end of the game'''
        
        # Validate the total_questions and score inputs
        if total_questions <= 0:
            raise ValueError("Total questions must be greater than 0.")
        if self._score < 0:
            raise ValueError("Score cannot be negative.")
        
        # Calculate the score ratio -> basecase is a total of 10 questions
        score_ratio = self._score / total_questions
        
        # Define thresholds for player levels
        if score_ratio <= 0.3: 
            return "HP Triva Novice. You need to read more books!"
        if score_ratio <= 0.6: 
            return "Trivia Enthusiast. Keep going!"
        if score_ratio <= 0.8: 
            return "Trivia Expert! You know your stuff!"
        return "Absolutely brilliant Master of HP Trivia! You crushed it!"

