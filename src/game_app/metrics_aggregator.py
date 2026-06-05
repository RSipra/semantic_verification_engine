"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Game performance metrics aggregator (latency, evaluation outcomes etc)
---------------------------------------------------------------------
Two roles (can be split into separate modules later):
1. Aggregation: collects and organizes performance metrics from mulitple sessions
2. TODO: Presentation: provides a readable summary of metrics for reporting and analysis.
"""
from typing import List, Literal
from collections import defaultdict
import numpy as np

from engine.dto import TurnResult
from game_app.constants import GameStatus
from game_app.types import SessionAggregates, SessionReport, PerformanceMetrics

## --- Aggregation ---
TIER_CATEGORIES = ["exact", "fuzzy", "sbert", "llm", "unresolved"]
SHIFT_LEFT_TIERS = ["exact", "fuzzy", "sbert"]
Scope = Literal["session", "batch", "global"]

# assign tier category to turn
def categorize_resolution_tier(resolution_tier) -> str:
    """Categorizes a turn result into a resolution tier."""
    tier = resolution_tier.lower()
    for category in TIER_CATEGORIES:
        if category in tier:
            return category
    return "unresolved"

# aggregate llm eval times from nested TurnResultList in SessionReport
def get_llm_time(evaluation) -> float | None:
    """Safely extracts optional LLM evaluation latency from an evaluation result."""
    return getattr(evaluation, "llm_eval_time_sec", None)

# helper to build tier distribution by question type and overall
def aggregate_tier_distribution(turn_results: List[TurnResult]
                                ) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
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
    tier_dist_by_evaluator, overall_tier_dist = aggregate_tier_distribution(
        session_report.all_turn_results)

    actual_question_count = session_report.questions_answered if session_report.questions_answered else 0

    return SessionAggregates(

        game_id=session_report.game_id,
        session_id=session_report.session_id,
        session_size=session_report.total_questions,

        session_quit = session_report.game_status == GameStatus.QUIT,   # for quit rate metric
        correct_count = sum(turn.evaluation.is_correct for turn in session_report.all_turn_results),

        evaluation_latency_events=[turn.evaluation.execution_time_sec 
                                   for turn in session_report.all_turn_results],

        # only EX and some FR turns have llm eval time, so filter for non null values
        llm_call_latency_events = [t for turn in session_report.all_turn_results
                                   if (t := get_llm_time(turn.evaluation)) is not None],

        tier_distribution_by_evaluator = tier_dist_by_evaluator,
        overall_tier_distribution = overall_tier_dist,

        executed_question_count = actual_question_count,
        unattempted_question_count = session_report.total_questions - actual_question_count)

# derive performance metrics from aggregated session data (can be extended to batch or global level)
def calculate_performance_metrics(scope_id : str,
                                  session_aggregates: list[SessionAggregates],
                                  scope: Scope = "session") -> PerformanceMetrics:
    """Calculates performance metrics from aggregated session(s) data."""

    # intialize counters and accumulators
    all_eval_latencies = []
    all_llm_latencies = []
    global_tier_distribution = defaultdict(int)
    global_by_eval = defaultdict(lambda: defaultdict(int))

    num_sessions = len(session_aggregates)
    total_turns = sum(agg.session_size for agg in session_aggregates)
    total_executed_questions = sum(agg.executed_question_count for agg in session_aggregates)
    total_unattempted_questions = sum(agg.unattempted_question_count for agg in session_aggregates)
    
    correct_answers = sum(agg.correct_count for agg in session_aggregates)
    accuracy_rate = (correct_answers/total_executed_questions)*100
    quit_rate = ((sum(agg.session_quit for agg in session_aggregates) / num_sessions) * 100
                 if num_sessions else 0)  # zero div error guard

    for session in session_aggregates:
        # latency event pool
        all_eval_latencies.extend(session.evaluation_latency_events)
        all_llm_latencies.extend(session.llm_call_latency_events)

        # overall tier distribution
        for tier, count in session.overall_tier_distribution.items():
            global_tier_distribution[tier] += count

        # evaluation resolution distribution (nested dict): {evaluator : {tier: count}}
        for evaluator, session_tier_dist in session.tier_distribution_by_evaluator.items():
            for tier, count in session_tier_dist.items():
                global_by_eval[evaluator][tier] += count   

    # proxies
    if total_executed_questions:
        sbert_usage = (global_tier_distribution.get('sbert',0)/total_executed_questions)*100
        llm_usage = (global_tier_distribution.get('llm',0)/total_executed_questions)*100
        shift_left_usage =( sum(global_tier_distribution.get(tier, 0) for tier in SHIFT_LEFT_TIERS
                                )/total_executed_questions)*100
    else:
        accuracy_rate = sbert_usage = llm_usage = shift_left_usage = 0    

    # latency metrics
    #  full evaluation latency (all tiers)
    if all_eval_latencies:
        p95_eval = np.percentile(all_eval_latencies, 95)
        avg_eval = np.mean(all_eval_latencies)
        max_eval = np.max(all_eval_latencies)
        min_eval = np.min(all_eval_latencies)
    else:
        p95_eval = avg_eval = max_eval = min_eval = 0

    # llm call latency (only for EX and FR outliers)
    if all_llm_latencies:
        p95_llm = np.percentile(all_llm_latencies, 95)
        avg_llm = np.mean(all_llm_latencies)
        max_llm = np.max(all_llm_latencies)
        min_llm = np.min(all_llm_latencies)
    else:
        p95_llm = avg_llm = max_llm = min_llm = 0

    return PerformanceMetrics(scope=scope,
                              scope_id=scope_id,
                              total_questions = total_turns,
                              executed_questions = total_executed_questions,
                              unattempted_questions = total_unattempted_questions,
                              num_sessions = num_sessions,

                              # latency (evaluation)
                              average_evaluation_latency= float(avg_eval), # convert from np.floating to python float
                              p95_evaluation_latency= float(p95_eval),
                              min_evaluation_latency= float(min_eval),
                              max_evaluation_latency= float(max_eval),

                              # latency (LLM calls only)
                              average_llm_call_latency = float(avg_llm),
                              p95_llm_call_latency = float(p95_llm),
                              min_llm_call_latency = float(min_llm),
                              max_llm_call_latency = float(max_llm),

                              # player outcomes
                              correct_answer_count = correct_answers,
                              accuracy_rate = accuracy_rate,   

                              # resolution patterns
                              tier_distribution_by_evaluator= {
                                  k: dict(v)for k, v in global_by_eval.items()},
                              overall_tier_distribution= dict(global_tier_distribution),
                              quit_rate = quit_rate,

                              # escalalation patterns
                              sbert_routing_share = sbert_usage, # compute proxy, %
                              llm_routing_share= llm_usage,      # latency proxy, %
                              shift_left_resolution_rate = shift_left_usage   # %
                              )
