"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Game Session Report storage helper
"""

import json
from datetime import datetime
import os

REPORT_DIR = "/app/runtime"

def generate_session_report_filename() -> str:
    """
    Generates a timestamped file path for storing session reports.
    Includes a human-readable timestamp to ensure each
    game run is uniquely identifiable and doesn't overwrite previous runs.

    Format:
        /app/runtime/session_reports_YYYY-MM-DD_HH-MM-SS.json

    Returns:
        str: Full file path for the session report output file.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"{REPORT_DIR}/session_reports_{timestamp}.json"


def save_session_reports(reports, path=None):
    """
    Saves a collection of SessionReport objects to a JSON file.

    This function serializes dataclass-based session reports into a JSON
    format suitable for debugging, auditing, and post-game analysis.

    If no path is provided, a timestamped filename is generated automatically
    to ensure each execution is uniquely stored without overwriting prior runs.

    Args:
        reports (list): List of SessionReport dataclass instances.
        path (str | None): Optional file path. If None, a timestamped
            path under the runtime directory is generated.

    Returns:
        None
    """
    os.makedirs(REPORT_DIR, exist_ok=True)

    if path is None:
        path = generate_session_report_filename()

    # Convert DTO to plain Python structures
    serializable_reports = [r.model_dump() for r in reports]

    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable_reports, f, indent=2, ensure_ascii=False)
