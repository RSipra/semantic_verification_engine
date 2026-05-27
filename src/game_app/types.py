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

from game_app.constants import SessionStatus

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
    status: SessionStatus | None = None
    # gameplay metrics
    score: int | None  = None
    total_questions: int | None  = None
    # observability
    duration_sec: float | None = None
    error: str | None = None
    # identity (safe UX layer fields)
    player_name: str | None = None
    house: str | None = None
    # extensibility
    metadata: dict[str, Any] | None = None
