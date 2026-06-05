"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Game Session Report storage helper
"""
from typing import Literal, List
import json
from datetime import datetime
import os
from pydantic import BaseModel

REPORT_DIR = "/app/runtime"

def generate_session_report_filename(category:str) -> str:
    """
    Generates a timestamped file path for storing session reports or
    session aggregates.
    Includes a human-readable timestamp to ensure each
    game run is uniquely identifiable and doesn't overwrite previous runs.

    Format:
        /app/runtime/session_{category}_YYYY-MM-DD_HH-MM-SS.json

    Returns:
        str: Full file path for the session report output file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{REPORT_DIR}/session_{category}_{timestamp}.json"

def generate_performance_metrics_filename(scope_id: str) -> str:
    """
    Generates a timestamped file path for storing aggregated session
    performance metrics.
    Includes a human-readable timestamp to ensure each
    game run is uniquely identifiable and doesn't overwrite previous runs.

    Format:
        /app/runtime/performance_metrics_{scope_id}_YYYY-MM-DD_HH-MM-SS.json

    Returns:
        str: Full file path for the performance metrics output file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{REPORT_DIR}/performance_metrics_{scope_id}_{timestamp}.json"

def save_session_reports(category: Literal["reports", "aggregates"], data: List[BaseModel], path=None):
    """
    Saves a collection of Pydantic session artifacts (reports or aggregates)
    to a JSON file.

    This function serializes structured session outputs into a JSON format
    suitable for debugging, auditing, and post-game analysis.

    If no path is provided, a timestamped filename is generated automatically
    to ensure each execution is uniquely stored without overwriting previous runs.

    Args:
        category (Literal["reports", "aggregates"]):
            Type of session artifact being saved.
        reports (List[BaseModel]):
            List of Pydantic models representing session data.
        path (str | None):
            Optional file path. If None, a timestamped file under the runtime
            directory is generated.

    Returns:
        None
    """
    os.makedirs(REPORT_DIR, exist_ok=True)

    if path is None:
        path = generate_session_report_filename(category)

    # Convert DTO to plain Python structures
    serializable_reports = [d.model_dump() for d in data]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable_reports, f, indent=2, ensure_ascii=False)

# save performance metrics of all sessions in the game
def save_performance_metrics(scope_id:str, metrics: BaseModel, path=None):
    """Saves performance metrics  """
    os.makedirs(REPORT_DIR, exist_ok=True)

    if path is None:
        path = generate_performance_metrics_filename(scope_id)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            metrics.model_dump(),
            f,
            indent=2,
            ensure_ascii=False
            )
