# HARRY_POTTER_TRIVIA/notebook_config.py
# ===================================================================
#      CONFIGURATION FOR THE DATA SCIENCE & NOTEBOOK WORKFLOW
# ===================================================================
#
# This file defines the file paths for the data preparation and
# analysis part of the project. It is used by the Jupyter notebooks
# and data scripts.
# ===================================================================

from pathlib import Path
import sys

# Import the function from its nested location within the src package
# This try/except block makes the import robust. It will work
# whether `pip install -e .` has been run or not.
try:
    from src.ds_utils.utils_paths import find_project_root
except ImportError:
    # Fallback if the package isn't installed in editable mode.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from ds_utils.utils_paths import find_project_root

# --- Path Definitions ---
# Find the project root ONCE using utility function.
PROJECT_ROOT = find_project_root()

# Define other paths relative to project root
DATA_DIR = PROJECT_ROOT / "data"
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_DIR = PROJECT_ROOT / "src"

# Data sub-directories 
RAW_DATA_DIR = DATA_DIR / "01_raw"
INTERMEDIATE_DATA_DIR = DATA_DIR / "02_intermediate"
MODELS_DIR = DATA_DIR / "03_models"
METRICS_DIR = DATA_DIR / "04_metrics"
FINAL_DATA_DIR = DATA_DIR / "05_final"
BOOK_TEXT = DATA_DIR / "06_books"
PL_LOGS = DATA_DIR / "07_pipeline_logs"
GENQ_DIR = DATA_DIR / "08_generated_questions"
THEMES_DIR = DATA_DIR / "09_themes"

# Prompts Directory
PROMPTS_DIR = SCRIPTS_DIR / "pipelines/generate_questions/prompts"

# Pipeline Reporting & Observability Paths
PIPELINE_LOGS_ROOT = DATA_DIR / "07_pipeline_logs"

MANIFESTS_DIR = PIPELINE_LOGS_ROOT / "manifests"
RUNS_DIR = PIPELINE_LOGS_ROOT / "runs"
LOGS_DIR = PIPELINE_LOGS_ROOT / "logs"

# Generated Content
GENERATED_QUESTIONS_DIR = DATA_DIR / "08_generated"

# TRACER-specific paths
# LLM runs
TRACER_LLM_GENERATION_DIR = SCRIPTS_DIR / "research/question_generation/tracer_dataset_generation"
TRACER_LLM_GEN_OUTPUTS_DIR = TRACER_LLM_GENERATION_DIR / "llm_outputs"
TRACER_SYNTHETHETIC_LLM_JUDGEMENT_DIR = SCRIPTS_DIR / "research/qa_validation/synthetic"

print("✅ Notebook config loaded.")
