'''PLAYER Class'''

class Player(object):
    ''' This class represents a player in a game session.'''
    
    def __init__(self, name: str, hogwarts_house: str):
        
        """Initialize the Player with a name and Hogwarts house."""
        
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
        self.name = name.strip().title()
        self.hogwarts_house = hogwarts_house.strip().title()
        # Initialize score to 0
        self.score = 0

    def __str__(self):
        return f"Player '{self.name}' is a member of {self.hogwarts_house} with a current score of {self.score}."

    def __repr__(self):
        return f"Player({self.name}, {self.hogwarts_house}, {self.score})"
    
    def __eq__(self, other):
        """Check if the other object is an instance of Player"""
        if isinstance(other, Player):
            return self.name == other.name and \
                   self.hogwarts_house == other.hogwarts_house
        return NotImplemented
        # can consider player_id as unique identifier for player later on. 

    def add_score(self, score: int):
        """Increase the player's score by 1 point"""
        self.score += 1
        return self.score
    
    def reset_score(self):
        """Return the player's score back to 0"""
        self.score = 0
        return self.score
    
    # getter function
    def get_score(self):
        """Return the player's score"""
        return self.score
    
    # getter function
    def get_name(self):
        """Return the player's name"""
        return self.name    
    
    # getter function
    def get_house(self):
        """Return the player's hogwarts house"""
        return self.hogwarts_house
      