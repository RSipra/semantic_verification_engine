"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

CLI MVP (core logic) -> constants module (data)

Centralized location for constants that are used across modules
------------------------------------------------------------------
"""
from enum import Enum

# Predefined number of questions per session
NUM_QUESTIONS_PER_SESSION = 10

# Name of the trivia dataset csv to use to extract questions from
MVP_TRIVIA_CSV_NAME = "cleaned_trivia_dataset_MVP_v0.csv"

# The main HP houses for players to select from
class House(str, Enum):
    """ 
    An enumeration for the four main Hogwarts houses.

    This class provides a fixed, type-safe set of constants used throughout
    the game for player house selection, validation, and related logic.
    By inheriting from `str`, members can also be treated as strings directly.
    """
    GRYFFINDOR = "Gryffindor"
    HUFFLEPUFF = "Hufflepuff"
    RAVENCLAW = "Ravenclaw"
    SLYTHERIN = "Slytherin"

# House heads for each Hogwart's House
class HouseHead(str, Enum):
    """ 
    An enumeration for the four main Hogwarts house heads.

    This class provides a fixed, type-safe set of constants. Its primary
    use is to supply the correct name for a Head of House in user-facing
    display messages. By inheriting from `str`, members can also be treated 
    as strings directly.

    Design Note: An Enum was chosen over simple strings to support future
    features. The intention is for the `HouseHead` to act as a 'game moderator'
    to control game logic and tone, making a type-safe constant the better
    long-term choice.
    """
    MCGONAGALL = "Professor McGonagall"
    SPROUT = "Professor Sprout"
    FLITWICK = "Professor Flitwick"
    SNAPE = "Professor Snape"

# Dictionary to map House to HouseHead    
HOUSE_TO_HEAD_MAPPING = {
    House.GRYFFINDOR: HouseHead.MCGONAGALL,
    House.HUFFLEPUFF: HouseHead.SPROUT,
    House.RAVENCLAW:  HouseHead.FLITWICK,
    House.SLYTHERIN:  HouseHead.SNAPE,
}

# A dictionary mapping House enums to rich style strings
HOUSE_STYLES = {
    House.GRYFFINDOR: "bold red on gold1",
    House.SLYTHERIN:  "bold green on grey70",  
    House.RAVENCLAW:  "bold blue on #CD7F32", 
    House.HUFFLEPUFF: "bold yellow3 on black"
}

# Wizard ranks for players based on their final score
class Rank(str, Enum):
    """ 
    An enumeration for the five ranks a player can obtain at the end of the game.

    This class provides a fixed, type-safe set of constants used throughout
    the game for player rank selection, validation, and related logic.
    By inheriting from `str`, members can also be treated as strings directly.
    """
    NOVICE = "Novice"
    ENTHUSIAST = "Enthusiast"
    EXPERT = "Expert"
    MASTER = "Master"
    UNKNOWN = "Unknown"
    