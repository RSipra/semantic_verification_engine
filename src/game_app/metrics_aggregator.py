"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Game performance metrics aggregator (latency, evaluation outcomes etc)
---------------------------------------------------------------------
Two roles (can be split into separate modules later):
1. Aggregation: collects and organizes performance metrics from mulitple sessions
2. Presentation: provides a readable summary of metrics for reporting and analysis.
"""
from typing import List

from engine.dto import TurnResult
from game_app.types import SessionAggregates, SessionReport

## --- Aggregation ---
TIER_CATEGORIES = ["exact", "fuzzy", "sbert", "llm", "unresolved"]

# assign tier category to turn
def categorize_resolution_tier(resolution_tier) -> str:
    """Categorizes a turn result into a resolution tier."""
    tier = resolution_tier.lower()
    for category in TIER_CATEGORIES:
        if category in tier:
            return category
    return "unresolved"

# helper to build tier distribution by question type and overall
def aggregate_tier_distribution(turn_results: List[TurnResult]) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    """
    Aggregates resolution-tier counts by evaluator and overall for a session.
    Args:
    - turn_results: List of TurnResult objects for a session.
    Returns:
    - tier_distribution_by_evaluator: Dict mapping evaluator types to dicts of tier counts.
        {question_type: {resolution_tier: count}}
    - overall_tier_distribution: Dict of overall tier counts across all evaluators.
        {tier_category: count}
    """
    # initialize dicts
    tier_distribution_by_evaluator: dict[str, dict[str, int]] = {}
    overall_tier_distribution = {category: 0 for category in TIER_CATEGORIES}

    for turn in turn_results:
        
        # create nested dict of evaluator -> tier -> count
        evaluator = turn.question_type.value    # Q type enum value
        tier = turn.evaluation.resolution_tier

        if evaluator not in tier_distribution_by_evaluator:
            tier_distribution_by_evaluator[evaluator] = {}

        if tier not in tier_distribution_by_evaluator[evaluator]:
            tier_distribution_by_evaluator[evaluator][tier] = 0

        tier_distribution_by_evaluator[evaluator][tier] += 1
        
        # second overall tier count (regardless of evaluator)
        tier_category = categorize_resolution_tier(tier)
        overall_tier_distribution[tier_category] += 1 
        
    return tier_distribution_by_evaluator, overall_tier_distribution

def aggregate_session_metrics(session_report: SessionReport) -> SessionAggregates:
    """
    Builds session-level aggregate metrics from a SessionReport.

    Extracts latency events and resolution-tier distributions
    for downstream performance analysis.
    """
    tier_dist_by_evaluator, overall_tier_dist = aggregate_tier_distribution(session_report.all_turn_results)
    
    return SessionAggregates(
        
        game_id=session_report.game_id,
        session_id=session_report.session_id,
        session_size=session_report.total_questions,
        
        evaluation_latency_events=[turn.evaluation.execution_time_sec 
                                   for turn in session_report.all_turn_results],
        
        # only EX and some FR turns have llm eval time
        llm_call_latency_events=[turn.evaluation.llm_eval_time_sec 
                                 for turn in session_report.all_turn_results 
                                 if turn.evaluation.llm_eval_time_sec is not None],
        
        tier_distribution_by_evaluator=tier_dist_by_evaluator,
        overall_tier_distribution=overall_tier_dist
    )


def calculate_performance_metrics(session_aggregates: list[SessionAggregates]):

## System snapshot per session

# {
#     "cpu_percent": ...,
#     "memory_mb": ...,
#     "timestamp": ...
# }

# SBERT calls{
#     "calls": n,
#     "avg_latency": ...,
#     "peak_latency": ...,
#     "memory_impact_estimate": ...
# }

## Infrastructure metrics
# Core VM metrics:
# CPU
# average CPU usage per session
# peak CPU usage (important for SBERT spikes)
# CPU saturation duration (% time > 70–80%)
# Memory
# steady-state memory (after warmup)
# peak memory (SBERT + inference bursts)
# memory delta per SBERT call (optional but useful)
# Latency under load
# p50 / p95 session latency
# p95 evaluator latency (important for EX paths)



## Application metrics per session
# total latency
# evaluator distribution
# resolution tier distribution
# per-question latency


# total session latency
# per-question latency distribution
# evaluator resolution pattern (exact / fuzzy / sbert / LLM)
# tier distribution (how often each resolution tier is hit)
# escalation rate (how often you “go up the stack”)

# # Operating Envelope =
#     (CPU ceiling,
#      Memory ceiling,
#      Latency ceiling,
#      Stability under repeated runs)


# -- derived metrics --
# llm_escalation_rate = overall_tier_distribution["llm"] / total_questions
# shift_left_resolution_rate =(exact +fuzzy +sbert) / total_questions

# Hardware Envelope (fixed)
#     ↓
# System Load Regime (your routing + LLM + SBERT behavior)
#     ↓
# Observed Metrics (latency, CPU spikes, tier distribution)

## --- Presentation ---
