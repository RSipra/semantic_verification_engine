"""
=======================================================================
SEMANTIC VERIFICATION ENGINER (Ref implementation: Harry Potter Trivia)
=======================================================================

CLI MVP (core logic) -> constants module (data)

Centralized location for constants that are used across modules
-----------------------------------------------------------------------
"""
from enum import Enum

# Predefined number of questions per session
NUM_QUESTIONS_PER_SESSION = 10

# Max number of questions allowed per session
MAX_QUESTIONS_PER_SESSION = 20

# Number of chances a player gets every question session
PLAYER_CHANCES = 3

# Custom Exceptions (can later go in a separate module)
class UserWantsToQuit(Exception):
    """Custom exception raised when the user types 'quit' at any prompt."""
    pass

## ---  Enums --- 
# TODO: shift to game_app/types.py

class SessionStatus(str, Enum):
    """ """
    ACTIVE = "active"
    EXHAUSTED = "exhausted"

class GameStatus(str, Enum):
    """
    Represents the terminal state of a trivia game session.
    This enum is used by the GameController to communicate the outcome
    of a single session back to the main application orchestrator.
    It then enables the main loop to make deterministic decisions about
    session lifecycle transitions (e.g. replay, exit, or graceful shutdown)

    Attributes:
        COMPLETED:The session finished normally after all questions were processed.
            The player may be prompted to replay.
        QUIT:The player terminated the session early via an explicit quit action.
        FAILED: The session terminated due to an unexpected runtime error or
            unrecoverable system failure (e.g. evaluator crash, missing data).
        LOST: The player exhuasted all chances causing the session to end.    
    """
    COMPLETED = "completed"
    QUIT = "quit"
    FAILED = "failed"
    LOST = "lost"

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
    House.GRYFFINDOR: "bold red3",
    House.SLYTHERIN:  "bold green3",
    House.RAVENCLAW:  "bold blue1",
    House.HUFFLEPUFF: "bold yellow1"
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
