'''
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

CLI MVP (core logic) -> player module (model)

------------------------------------------------------------------
'''
import HPtrivia_game.constants as const


class Player:
    ''' This class represents a player in a game session.'''
    
    def __init__(self, name: str, hogwarts_house: const.House):
        """Initialize the Player with a name and Hogwarts house and all other attributes."""
        self._name = name.strip().title()
        self._hogwarts_house = hogwarts_house
        self._score = 0
        self._chances_left = const.PLAYER_CHANCES 

    def __str__(self):
        return (
            f"Player '{self.name}' is a member of House {self.house.value} "
            f"with a current score of {self.score}."
        )

    def __repr__(self):
        """
        Return the official, developer-friendly string representation of the Player.
        """
        return (
            f"{self.__class__.__name__}("
            f"name='{self.name}', "
            f"hogwarts_house={repr(self.house)}, "
            f"score={self.score}, "
            f"chances_left={self.get_chances}"
            f")"
        )
    
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
    
    @property    
    def get_chances(self) -> int:
        """Returns the current number of chances left."""
        return self._chances_left
    
    def add_score(self, points=1):
        '''Increase the player's score by 1 point'''
        self._score += points
        return self._score
    
    def lose_chance(self):
        """Reduces the player's chances by 1 if any are left."""
        if self._chances_left > 0:
            self._chances_left -= 1
    
    def reset_stats(self):
        """Resets the player's score and chances for a new round."""
        self._score = 0
        self._chances_left = const.PLAYER_CHANCES

    def has_chances_left(self) -> bool:
        """Returns True if the player has 1 or more chances, False otherwise."""
        return self._chances_left > 0
    
    def find_player_wizard_rank(self, total_questions: int) -> const.Rank:
        """
        Calculates and returns the player's rank category based on score.
        Returns a string key like 'NOVICE', 'EXPERT', etc.
        """
        # Prevent zero-division error
        if total_questions <= 0:
            return const.Rank.UNKNOWN
        
        # calculate ratio for rank thresholds
        score_ratio = self._score / total_questions
        
        if score_ratio <= 0.3: 
            return const.Rank.NOVICE
        if score_ratio <= 0.6:
            return const.Rank.ENTHUSIAST
        if score_ratio <= 0.8:
            return const.Rank.EXPERT
        return const.Rank.MASTER
