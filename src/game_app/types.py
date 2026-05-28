"""
=======================================================================
SEMANTIC VERIFICATION ENGINER (Ref implementation: Harry Potter Trivia)
=======================================================================

CLI MVP (core logic) -> Types
-----------------------------------------------------------------------
"""

from typing import TypeAlias, Any
from dataclasses import dataclass
from core.models import (RuntimeStandard_Green, RuntimeMCQ_Green,
                         RuntimeStandard_Blue, RuntimeMCQ_Blue)

from game_app.constants import GameStatus, SessionStatus, NUM_QUESTIONS_PER_SESSION, House

# NOTE:
# These Question type hints are only used to make function signatures clearer.
# Question is the main type used across the system (router/controller level).
# Evaluators and subrouters use the actual runtime models directly and do not
# rely on additional type aliases for MCQ/FR/EX separation.
#
# The router is the only place that decides which evaluator is used.
# These type hints do not affect runtime behavior.
# >> If runtime models or router logic change, these type hints will need to 
#    be updated.

Question: TypeAlias = (
    RuntimeStandard_Green |
    RuntimeMCQ_Green |
    RuntimeStandard_Blue |
    RuntimeMCQ_Blue
)

@dataclass
class SessionReport:
    """Standard format for Game Controller status return to Main"""
    game_id : str                                   # unique game id
    total_questions: int                            # session size
    # identity (safe UX layer fields)
    player_name: str                                # for ui
    house:  House                                   # for ui
    session_id: int = 0                             # serial id within game id
    session_status: SessionStatus = SessionStatus.ACTIVE   # Active | Exhausted
    game_status: GameStatus | None = None           # completed, lost, failed, quit
    # gameplay metrics
    score: int | None  = None                       # player score
    questions_answered: int | None  = None          # questions attempted by player 
    # observability
    duration_sec: float | None = None               # time taken to complete given session
    error: str | None = None                        # report cause when session status != completed    
    # extensibility
    metadata: dict[str, Any] | None = None

@dataclass
class Session:
    """Carries session states within a game"""
    game_id : str                                          
    remaining_pool: list[str]                              # questions available for next session allocation (order preserved)
    questions: list[Question] | None                       # current session question batch
    session_status: SessionStatus = SessionStatus.ACTIVE   # Active | Exhausted
    session_size: int = 0
