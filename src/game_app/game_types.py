"""
=======================================================================
SEMANTIC VERIFICATION ENGINER (Ref implementation: Harry Potter Trivia)
=======================================================================

CLI MVP (core logic) -> Types
-----------------------------------------------------------------------
TODO: Metrics Granularity Alignment (MVP STABILITY)

There is currently ambiguity between:
- Turn (atomic unit)
- Session (batch of turns in one run)
- Game (full CLI execution containing sessions)
- Global (future cross-run aggregation)

Current MVP definition:
- TurnResult = primary source of truth for all metrics
- Session = execution batch (grouping only, not analytical identity)
- Game = full CLI run (structural container only)
- Global = not implemented yet

Action for post-MVP:
- Align controller + metrics layer on a single granularity model
- Decide whether SessionReport is UX-only or analytics input
- Avoid introducing new ID systems or restructuring hierarchy during demo phase

MVP constraint:
- No refactors to identity model
- Metrics must be derivable from existing TurnResult + SessionReport only
"""

from typing import TypeAlias, Any, Literal
from pydantic import BaseModel, Field
from core.models import (RuntimeStandard_Green, RuntimeMCQ_Green,
                         RuntimeStandard_Blue, RuntimeMCQ_Blue)

from engine.dto import TurnResult
from game_app.constants import GameStatus, SessionStatus, House

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

class SessionReport(BaseModel):
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
    all_turn_results: list[TurnResult] = Field(default_factory=list) # List of all question turn reports
    # observability
    duration_sec: float | None = None               # time taken to complete given session
    error: str | None = None                        # report cause when session status != completed
    # extensibility
    metadata: dict[str, Any] | None = None

class Session(BaseModel):
    """Carries session states within a game"""
    game_id : str                                          
    remaining_pool: list[str]                              # questions available for next session allocation (order preserved)
    questions: list[Question] | None                       # current session question batch
    session_status: SessionStatus = SessionStatus.ACTIVE   # Active | Exhausted
    session_size: int = 0

class SessionAggregates(BaseModel):
    """Raw and structured signals for generating session performance metrics"""
    game_id: str
    session_id: int
    session_size: int
    session_quit: bool = False   # whether player quit during this session (used for quit rate metric)
    correct_count: int = 0       # number of questions answered correctly in session (used for accuracy metric)
    executed_question_count: int   # actual question count player answered by player (< session size if player uses up chances and loses)
    unattempted_question_count: int  # questions remaining in session the player couldn't get to

    # latency
    evaluation_latency_events: list[float] = Field(default_factory=list)  # list of evaluation times for questons in session
    llm_call_latency_events: list[float] = Field(default_factory=list)    # list of only llm api call time when made

    # evaluation outcomes
    tier_distribution_by_evaluator: dict[str, dict[str, int]] = Field(default_factory=dict)  # e.g {FR: {'primary_semantic_match: count}}
    overall_tier_distribution: dict[str, int] = Field(default_factory=dict)  # e.g {'sbert': count}
    
class PerformanceMetrics(BaseModel):
    """
    Derived performance metrics calculated from SessionAggregates.
    Can be a single session, batch, or global aggregations. 
    """
    scope: Literal["session", "batch", "global"] 
    scope_id: str    # free-form run label / aggregation identifier e.g. 'July_202X_batch' or 'global_all_runs'
    # aggregation metadata
    total_questions: int
    executed_questions: int
    unattempted_questions: int
    num_sessions: int = 1

    # latency (evaluation)
    average_evaluation_latency: float 
    p95_evaluation_latency: float
    min_evaluation_latency: float 
    max_evaluation_latency: float 

    # latency (LLM calls only)
    average_llm_call_latency: float
    p95_llm_call_latency: float 
    min_llm_call_latency: float 
    max_llm_call_latency: float

    # player outcomes
    correct_answer_count: float
    accuracy_rate: float    # correct_answer_count / total_turns

    # resolution patterns
    tier_distribution_by_evaluator: dict[str, dict[str, int]]
    overall_tier_distribution: dict[str, int]
    quit_rate: float | None = None      # (sessions where game_status == QUIT) / total sessions

    # escalalation patterns
    sbert_routing_share: float | None = None    # compute proxy
    llm_routing_share: float | None = None      # latency proxy
    shift_left_resolution_rate: float | None = None   # (exact + fuzzy + sbert) / total_turns -> non-LLM resolution
