"""
HARRY POTTER TRIVA GAME - Automated Question Generation Pipeline using PREFECT.
===================================================================================

This module orchestrates the end-to-end flow of generating trivia questions using
Google's Gemini models (Pro & Flash). It handles API interactions, token accounting,
data lineage tracking via manifests, and robust error handling.

KEY COMPONENTS:
    - Model-per-Task routing (Pro for EX/MCQ, Flash for FR)
    - Prefect orchestration (Retries, Logging, Artifacts)
    - Lineage tracking: Generates Manifests (intent), Prefect logs (progress), 
      and Receipts (results).
    - Flexible Execution Modes: Supports *Standard* (Full), *Pilot* (Partial), 
      *Demo (1-Chapter)*, and *Thematic* (cross-book) runs via CLI arguments
      and in notebook.
    - Extensible architecture: Designed for horizontal scaling; 
      configuration-driven strategy allows for easy adaptation to parallel model 
      execution (swimlanes to run multiple models at once, Pro / Flash) in 
      future iterations.
    - Scalable cost model: Designed for the Free Tier with built-in "throttles" 
      (rate limiting, batching) that can be instantly lifted via config for 
      high-throughput Pay-As-You-Go execution.  
 
PIPELINE ARCHITECTURE:
    1. **Initialization:** Setup Run IDs, Logging, and API connections. Saves
    the 'Manifest'.
    2. **Strategy (Batch) Loop:** Iterates through defined strategies (EX, MCQ, FR).
    3. **Chapter (Job) Loop:** Batches chapters, prepares prompts, and calls the API.
       - Includes 'circuit breaker' logic (stops after 5 consecutive failures).
       - Includes rate limiting logic (for Google Free-Tier utilization).
    4. **Response output ETL & Validation:** parses JSON responses, validates safety, 
       calculates granular token costs, and appends to JSONL.
    5. **Reporting:** Generates a Markdown Dashboard Artifact and a final JSON Receipt. 
    
USAGE:
    **Terminal (CLI):**
    # 1. Standard Full Run: over all chapters of Books 3, 4, 7 
    $ python scripts/generate_questions.py --books BOOK_3 BOOK_4 BOOK_7
    # 2. Partial pilot: e.g.  Book 4, MCQ questions only, first 5 chapters
    $ python scripts/generate_questions.py --books BOOK_4 --tasks MCQ_Generation --limit 5
    # 3. Canary (targeted) run: Book 3, only chapters 15, 16
    $ python scripts/generate_questions.py --books BOOK_3 --chapters 15 16
    # 4. Demo: Book 3, chapter 1, Factual Recall questions (FR)
    $ python scripts/generate_questions.py --books BOOK_3 --tasks FR_Generation --limit 1
    # 5. Thematic run: using "Theme" dir / excerpt "{theme_prefix}_{descriptive_text}_{number}.txt" 
    #    with batch size being the excerpts to be used within the same API call 
    #    NOTE: Book.THEME_DOBBY will need to defined in Book Enum
    $ python scripts/generate_questions.py --books THEME_DOBBY --batch-size 10 
    
    **Python (Notebook/Script):** same examples as CLI
    >>> from scripts.generate_questions import generate_questions_pipeline
    >>> from ds_utils.ds_constants import Book
    >>> # 1. Standard Full Run
    >>> generate_questions_pipeline(target_books=[Book.BOOK_3, Book.BOOK_4, Book.BOOK_7])
    >>> # 2. Partial Pilot
    >>> generate_questions_pipeline(target_books=[Book.BOOK_4], tasks_to_run='MCQ_Generation', chapter_limit=5)
    >>> # 3. Canary Run (troubleshooting)
    >>> generate_questions_pipeline(target_books=[Book.BOOK_3], target_chapters=[15, 16])
    >>> # 4. Demo Run
    >>> generate_questions_pipeline(target_books=[Book.BOOK_3],chapter_limit=1)
    >>> # 5. Thematic Run
    >>> generate_questions_pipeline(target_books=[Book.THEME_DOBBY], batch_size=10)
  
-----------------------------------------------------------------------------------
BEST PRACTICES & CONSTRAINTS:

1.  **Limited Runs (Surgical Testing):**
    When using `--limit` or `--chapters` to target specific content, it is strongly
    recommended to run **ONE BOOK AT A TIME**.
    * *Risky:* `--books BOOK_3 BOOK_4 --limit 1` (Ambiguous result order).
    * *Safe:* Run the command twice, once for each book.

2.  **Thematic / Cross-Source Generation:**
    To generate questions that require connecting dots across multiple books (e.g., 
    "Dobby's Arc"), do not try to cherry-pick chapters via CLI arguments.
    * **Methodology:** Create a "Thematic Book" folder (e.g., `data/06_books/theme_dobby/`)
        containing text files with standardized naming "{theme_prefix}_{descriptive_text}_{number}.txt"
        of the relevant excerpts.
    * **Context Window:** To allow the model to synthesize information across these excerpts, 
        they must be sent in a **single API call**.
    * **Execution:** Run with a `--batch-size` equal to the number of files 
        (e.g., `--batch-size 10`) so they are all loaded into one prompt context.
------------------------------------------------------------------------------------
Author: Reema Sipra
Date: November 2025
License: MIT 

Attribution:
    This pipeline architecture and strategy (key components listed such as model-per-task,
    flexible execution modes) were designed by the author. 
    The core generation logic was refactored from the author's original 
    `run_experiments_v2.py` script. Implementation of the Prefect orchestration 
    layer (Tasks, Flows, Artifacts) and specific logging patterns were developed 
    with collaborative assistance from LLM tools (Gemini 3 Pro). The AI acted as a pair 
    programmer for code refinement, troubleshooting complex logic, and iterative 
    design of MLOps best practices.
-----------------------------------------------------------------------------------
"""
## SETUP
import os
import sys
from datetime import datetime, timezone
import time
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import json
import uuid
from dotenv import load_dotenv
import google.generativeai as genai
from prefect import flow, task, get_run_logger #pipeline orchestrator
from prefect.artifacts import create_markdown_artifact
from rich.console import Console
from rich.markdown import Markdown
# IMPORT PROJECT CONFIGURATION
# Using the "Src Layout" (pip install -e .)
from ds_utils.ds_constants import Book
from scripts.pipelines.pipeline_config import GENERATION_STRATEGY
import ds_utils.notebook_config as nb_cfg

## CONSTANTS

# Paths
PROMPTS_DIR = nb_cfg.PROMPTS_DIR
OUTPUT_DIR = nb_cfg.GENERATED_QUESTIONS_DIR
CONFIG_PATH = nb_cfg.PROJECT_ROOT / 'config.env'

# Reporting Paths (centralized)
PIPELINE_LOGS_ROOT = nb_cfg.PIPELINE_LOGS_ROOT
MANIFESTS_DIR = nb_cfg.MANIFESTS_DIR
RUNS_DIR = nb_cfg.RUNS_DIR 
LOGS_DIR = nb_cfg.LOGS_DIR
# safety check: ensure directories that will be written to exist immediately
for d in [OUTPUT_DIR, MANIFESTS_DIR, RUNS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Standardized unique identifier for this question_gerantion script with version
PIPELINE_ID = "pipe_q_gen_v00"
# Pipeline settings (circuit breaker limit - how many failed runs before aborting pipeline)
MAX_FAILURES = 5

# GENERATION_STRATEGY: Predefined models for each question type (model-per-type based 
# on experimentation) imported from src/ds_utils/ds_constants

## TASKS AND HELPERS

def init_run_stats() -> dict:
    """Creates the empty accumulator dictionary for the pipeline run."""
    return {
        "total_input": 0,
        "total_output": 0,
        "total_billed": 0,
        "total_questions": 0,
        "chapters_processed": 0,
        "models_used": set()
    }
    
def short_uuid(n=8) -> str:
    """
    Generates a concise, random alphanumeric identifier based on UUID4.
    This is used to create readable unique IDs for pipeline runs, batches, and jobs
    where a full 32-character UUID would be too verbose for filenames or logs.

    Args:
        n (int, optional): The length of the identifier to generate. Defaults to 8.

    Returns:
        str: A random hexadecimal string of length `n` (e.g., "a1b2c3d4").
    """    
    return uuid.uuid4().hex[:n]  

@task # filter for flexibility in case not planning to run all question types in GENERATION_TYPE (default is all)
def filter_strategy(strategy: List[Dict], tasks_to_run: Optional[List[str]] = None) -> List[Dict]:
    """
    Selects specific generation tasks to run. 
    If tasks_to_run is None or empty, returns the full strategy (Default).
    """
    logger = get_run_logger()

    # Default: run everything
    if not tasks_to_run:
        logger.info("🌍 No filter applied. Running FULL strategy.")
        return strategy

    # filter: select specific tasks
    active_strategy = [config for config in strategy if config['task_name'] in tasks_to_run]

    # Validation: Warn if nothing matched (e.g. typo)
    if not active_strategy:
        logger.warning("⚠️ Filter '%s' matched 0 tasks! Check your spelling.",tasks_to_run)
        return []

    logger.info("Strategy filtered to %s tasks: %s", len(active_strategy),tasks_to_run)
    return active_strategy

@task
def configure_file_logging(run_id: str):
    """
    Attaches a FileHandler to the Prefect logger so logs are saved to disk
    in addition to the Prefect UI/Database.
    This allows for persistent, grep-able log files that survive local database clears.
    **Note:** This method was developed with assistance from an LLM (Gemini 3 pro).
    """
    # Path setup
    log_dir = LOGS_DIR
    # log filename
    log_file = log_dir / f"{run_id}.log"

    # Hook into the existing 'prefect' logger
    # Note: This ensures we capture both our logs AND Prefect's system logs
    logger = logging.getLogger("prefect")

    # Create the File Handler (The Writer)
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # Create formatter: Define Format (Time | Level | Message)
    formatter = logging.Formatter('%(asctime)s | TRACE:%(run_id)s | %(levelname)s | %(message)s')
    fh.setFormatter(formatter)

    # Add handler to logger (to send a copy to this local file handler as well)
    logger.addHandler(fh)

    return str(log_file)

@task  #configure the API
def configure_api(config_path: Path) -> None:
    """Loads environment variables and configures the Gemini API."""

    # 1. Safety check: confirm file exists
    if not config_path.exists():
        get_run_logger().warning("Config file not found at: %s", config_path)
        get_run_logger().warning("Attempting to use system environment variables...")

    # 2. load config
    load_dotenv(dotenv_path=config_path)

    # 3. verify the key (this works for both local and cloud/CI dep) > config injected directly here
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY not found in the config file.")

    # 4: configure api 
    genai.configure(api_key=api_key)  # type: ignore

# select different dirs for book vs. thematic runs    
def determine_target_folder(target_books: List[Book]) -> str:
    """
    Selects the correct data subdirectory based on the target type.
    Logic:
        - If ANY requested target contains "THEME" in its name, 
          we assume a Thematic Run and switch to the themes folder.
        - Otherwise, defaults to the standard books folder.
    Args:
        target_books (List[Book]): A list of Book Enum members defining which 
                      books to process (e.g., [Book.BOOK_3, Book.BOOK_4]).    
    """
    # Check if any enum member is a Theme (e.g. Book.THEME_DOBBY)
    is_thematic = any("THEME" in b.name for b in target_books)
    
    if is_thematic:
        return "09_themes"
    return "06_books"   

@task # get list of Paths for all the chapters for select book ready for formatting the prompt template per run
def get_chapters(target_books: list[Book], 
                 target_book_folder: str = "06_books",
                 chapter_filter: Optional[List[int]] = None,
                 chapter_limit: Optional[int] = None) -> List[Path]:
    """
    Scans, filters, and limits chapter files.

    **Processing Logic & Precedence:**
    1. **Scan:** Find files matching the Target Books.
    2. **Filter first:** Keep only specific chapter numbers (if `chapter_filter` is set).
    3. **Sort second:** Order alphanumerically.
    4. **Limit last:** Slice the top N files (if `limit` is set)
    *Example:* Requesting chapters `[15, 16, 17]` with `limit=1` returns only `[15]`.
    This is useful for isolating and re-running specific chapters that failed
    without processing the whole book again."
    
    **Critical Assumption (File Naming Contract):**
    This task assumes all files in `target_book_folder` follow a strict naming 
    convention generated by the `extract_hp_corpus' script. 
    - Format: `"{book_prefix}_{chapter_number}.txt"`
    - Example: `prisoner_of_azkaban_chapter_1.txt`
    
    The logic relies on `split('_')[-1]` to extract the chapter number for filtering/sorting.
    Files violating this format will be skipped or cause sorting errors.
    
    Args:
        target_books (List[Book]): A list of Book Enum members defining which 
                                   books to process (e.g., [Book.BOOK_3, Book.BOOK_4]).
        target_book_folder (str): The subdirectory within 'data/' to search. 
                                  Defaults to "06_books".
        chapter_filter (List[int], optional): Allows for optional filtering of content by 
                                  chapter number (e.g. [1, 5]).
        limit: Maximum number of chapters to return.

    Returns:
        List[Path]: A list of pathlib.Path objects for every matching text file,
                    sorted alphanumerically to ensure deterministic processing order.
    """
    books_dir = nb_cfg.DATA_DIR / target_book_folder
    # convert Enums to a tuple of strings for startswith()
    prefixes = tuple(book.value for book in target_books)

    # find all the chapter files by book name (prefix in the filename)
    relevant_file_paths = [p for p in books_dir.iterdir() if p.name.startswith(prefixes)]

    # filter by chapter only when requested
    if chapter_filter:
        # initialize filtered list
        filtered_files = []
        for p in relevant_file_paths:
            try:
                # leveraging standardized chapter names "book_name_chapter_12.txt"
                num = int(p.stem.split("_")[-1])
                if num in chapter_filter:
                    filtered_files.append(p)
            except ValueError:
                pass

    selected_chapter_paths = filtered_files
   # 3. Sort
    sorted_files = sorted(selected_chapter_paths)

    # 4. Apply  chapter limit
    if chapter_limit:
        sorted_files = sorted_files[:chapter_limit]

    return sorted_files

# flag if run is 'full_book' (i.e. all + full chapter runs)
def get_run_scope(chapter_limit: Optional[int], chapter_filter: Optional[List[int]]) -> str:
    """
    Determines if this is a 'full_book' run or a 'partial_pilot' based on constraints.
    Logic:
        - If ANY limit or filter is applied -> "partial_pilot"
        - If NO constraints are applied -> "full_book"
    """
    if chapter_limit is not None or chapter_filter is not None:
        return "partial_pilot"
    return "full_book"

@task
def save_run_manifest(run_id: str, pipeline_id: str, active_strategy: list, 
                      target_books: List[Book], chapters: list, 
                      run_timestamp: str, run_scope: str) -> None:
    """
    Saves the execution plan (*recipe*) before execution starts. This is to help distinguish 
    between attempted runs (e.g aborted, crashed) vs. successful runs (with full reporting, 
    artifacts)
    
    Args:
        run_id: The unique UUID for this pipeline execution.
        pipeline_id: The versioned identifier for this script logic (e.g., 'pipe_q_gen_v0').
        active_strategy: The list of active (filtered if applicable) generation configs 
        (models, prompts) to be executed.
        target_books: The specific list of Book enums targeted in this run.
        chapters: The specific list of chapters file paths selected for this run.
    """
    # path to save run manifest to
    manifest_dir = MANIFESTS_DIR

    # Edit question_type dict to json compatible formats
    formatted_strategy = []
    for config in active_strategy:
        clean = config.copy()
        if isinstance(clean.get('prompt_file'), Path):
            clean['prompt_file'] = clean['prompt_file'].name  # drop folder name
        # Remove schema class from log (not compatible with json)
        clean.pop('json_response_schema', None)
        formatted_strategy.append(clean)

    manifest = {
        "identifiers": {"run_id": run_id, "pipeline_id": pipeline_id},
        "run_timestamp": run_timestamp,
        "scope": {
            "type": run_scope,
            "target_books": [b.name for b in target_books],
            "total_chapters": len(chapters), 
            "chapter_files": [p.name for p in chapters] 
        },
        "strategy": formatted_strategy
    }
    # Save manifest with standardized name
    filename = f"{pipeline_id}_{run_id}_manifest.json"
    with open(manifest_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    get_run_logger().info("Manifest saved: %s", filename)

# Get an estimate of the template's token count ONCE (cached input) at the start of run
@task(retries=2)
def measure_template_tokens(model_name: str, prompt_path: Path) -> int:
    """
    Calculates the token count of the raw prompt template (Metric 1).
    We run this ONCE per strategy to establish the 'Cached' baseline.
    """
    # read the raw template (before formatting -> adding the chapter text, source_info etc)
    template_text = prompt_path.read_text(encoding="utf-8")
    # ask the model to count it
    model = genai.GenerativeModel(model_name)  # type:ignore
    response = model.count_tokens(template_text)

    return response.total_tokens

# flexible chunking of chapters for api calls
def chunk_list(chapter_list: list, batch_size: int):
    """
    Yields successive chunks from the list. Defines chunk sizes to allow for using
    multiple chapters to be processed together instead of just one at a time.
    Args:
        chapter_list (list): list of chapter Paths to iterate through
        batch_size (int): the number of chapters per chunk
    """
    for i in range(0, len(chapter_list), batch_size):
        yield chapter_list[i:i + batch_size]

@task  # prepare prompt template + text insersts (chapters for ground, chapter reference)
def prepare_prompt(chapter_path: List[Path], prompt_path:Path) -> str:
    """
    Reads a batch of chapter files and a prompt template to construct the final prompt.
    
    It combines the text of two chapters (batching) and dynamically generates
    the 'valid_source_list' based on the filenames provided. It can handle reading a 
    single chapter as well.

    Args:
        chapter_paths (List[Path]): A list of paths to the text files (chapters) to process.
        prompt_path (Path): The path to the text file containing the prompt template.

    Returns:
        str: The fully formatted prompt string ready for the API.
    """
    # get the prompt template location for the specific experiment run and read it
    prompt_template = prompt_path.read_text(encoding="utf-8")

    # Integrity checks for the prompt template from unit testing
    #1. incase the prompt template is empty
    if not prompt_template or prompt_template.isspace():
        raise ValueError(f"Prompt template file is empty: {prompt_path}")
    #2. if the prompt template doesn't have a placeholder for the chapters (source text)    
    if "{source_text}" not in prompt_template:
        raise ValueError("Prompt template is missing the required '{source_text}' placeholder.")
    #3. if the prompt template doesn't have a placeholder for the source info (references)    
    if "{valid_source_list}" not in prompt_template:
        raise ValueError(f"Prompt template {prompt_path} is missing the required '{{valid_source_list}}' placeholder.")

    # Read and combine the two source text / chapter files
    source_texts = []
    source_info = []
    for path in chapter_path:
        # read the chapter
        text_content = path.read_text(encoding="utf-8")
        # Prevent silent failure (empty source files)
        if not text_content or text_content.isspace():
            raise ValueError(f"Source file is empty or contains only whitespace: {path}")
        # add chapter to source_text list
        source_texts.append(text_content)
        # extract the ref. from the chapter file name -> standardized as "Bookname_chapter_number"
        source_info.append(path.stem.replace("_", " ").title())

    # prepare chapters and source_info into str format   
    combined_text = "\n\n--- END OF CHAPTER ---\n\n".join(source_texts) 
    formatted_options_str = "\n".join(f"- \"{option}\"" for option in source_info) 

    # asselmble and return the final prompt
    final_prompt = prompt_template.format(
        source_text=combined_text,
        valid_source_list=formatted_options_str
        )
    return final_prompt      

# To handle the 429 error caused by time sliding window (exceeding RPM limit for free-tier) 
# -> pipeline retries with larger delays.
@task(retries=5, retry_delay_seconds=[30, 60, 90, 120, 180])
def make_api_call(final_prompt:str, config: dict):
    """
    Calls Gemini with built-in retries and specific generation parameters.
    
    Args:
        final_prompt: The finalized prompt string
        config: A dictionary containing 'model_name', 'temperature', etc.
    """
    logger = get_run_logger()

    # 1. Extract the model name for the general strategy config dict
    model_name = config.get('model_name')
    if not model_name:
        raise ValueError("Configuration missing required key: 'model_name'")
    # create model instance
    model = genai.GenerativeModel(model_name)  # type: ignore

    # 2. Create Generation Config
    gen_config = genai.GenerationConfig(  # type: ignore
        temperature=config.get('temperature', 0.7),
        top_p=config.get('top_p', 0.95),
        max_output_tokens=config.get('max_output_tokens', 12000),
        candidate_count=config.get('candidate_count', 1),
        response_mime_type="application/json",
        response_schema = config.get("json_response_schema")
    )
    # 3. Call API
    try:
        response = model.generate_content(final_prompt, generation_config=gen_config)
        return response
    except Exception as e:
        logger.error("API Call failed for %s: %s", model_name, e)
        raise e

# helper to parse the json output from the API response object
@task
def extract_json_from_response(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Attempts to parse JSON from a string, handling potential Markdown wrapping.
    Returns None if parsing fails.
    """
    # 1. model mime respones works and returns correct json format (happy path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Fail-safe. Model returns the response in incorrect foramt (str or wrapped in md)
    #  look for json delimiters '[' and ']'
    try:
        start = text.find('[')  # returns -1 if not found
        end = text.rfind(']')   # returns -1 if not found

        if start != -1 and end != -1:  # make sure both delimiters exist
            json_str = text[start : end + 1]  # then parse
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 3. parsing fails
    return None

# compile the Strategy (pipeline run) metadata
def create_strategy_batch_metadata(pipeline_run_id: str,  # Level 1 (pipeline run) full script
                                   batch_id: str,         # Level 2 (strategy) question type batch
                                   job_id: str,           # Level 3 (job) api call
                                   run_timestamp: str, 
                                   strategy: dict,
                                   source_filenames: List[str]) -> dict:
    """
    Constructs the standardized metadata object for a generation batch.
    Merges static strategy config with dynamic runtime context.
    """
    return{
        "identifiers": {
            "pipeline name" : PIPELINE_ID,
            "pipeline_run_id": pipeline_run_id,     # Run: [parent] full script run
            "batch_id": batch_id,                   # Strategy: [group] question type batch 
            "job_id": job_id                        # Job: [child] specific API call
        },
        "timestamp": run_timestamp,                 # pipeline run timestamp
        # context
        "source_files": ", ".join(source_filenames),   # job level
        "task_type": strategy.get('task_name'),
        "prompt_template": strategy['prompt_file'].name,   # w/o file ext
        "model_name": strategy.get('model_name'),
        # model hyperparameters for current batch / strategy (question type)
        "hyperparameters": {
            "temperature": strategy.get('temperature'),
            "top_p": strategy.get('top_p'),
            "max_tokens": strategy.get('max_output_tokens'),
            "candidate_count": strategy.get('candidate_count', 1)
        }
    }

# response processing helper: check if api call accepted by model and response present
def check_safety_and_feedback(response, full_metadata: Dict[str, Any], job_id: str, logger) -> bool:
    """
    response processing layer 1: forensics, if successful returns True,
    updates metadata with API status (prompt_feedback, finish_reason),
    else returns False if the call was blocked.
    """
    # Check if the model refused to generate content (Safety Block)
    finish_reason = "UNKNOWN"  # default
    if hasattr(response, 'candidates') and response.candidates:
        finish_reason = response.candidates[0].finish_reason.name

    prompt_feedback = getattr(response, 'prompt_feedback', None)

    # update metadata in-place so we have a record even if it fails
    full_metadata["finish_reason"] = finish_reason
    full_metadata["prompt_feedback"] = str(prompt_feedback)

    # 1. Safety Block Check
    if finish_reason == "SAFETY":
        logger.error("⛔ [job id: %s] Safety Block triggered. Feedback: %s", job_id, prompt_feedback)
        return False 

    # 2. Empty/Malformed Response Check
    if not hasattr(response, 'candidates') or not response.candidates:
        logger.error("[job id: %s] No candidates found in response object.", job_id)
        return False

    return True

# response output processing helper: calculate token counts
def calculate_token_metrics(response, full_metadata: dict, 
                            template_token_count: int) -> Tuple[int, int, int]:
    """
    response processing layer 2: accounting. Updates metadata with granular token
    breakdown. Returns (Total, Input, Output) counts.
    """
    # Extract raw numbers from the API
    usage = getattr(response, 'usage_metadata', None)
    api_total_input = getattr(usage, 'prompt_token_count', 0)
    api_output = getattr(usage, 'candidates_token_count', 0)
    api_total_billed = getattr(usage, 'total_token_count', 0) # total tokens

    # Calculate your granular custom metrics
    cached_input = template_token_count   # prompt template w/o formatting (cached_input)
    uncached_input = max(0, api_total_input - cached_input)  # chapter_text, source_info tokens 
    processing_tokens = api_total_billed - (api_total_input + api_output)  # hidden tokens

    # Pack counts into a metadata dict
    full_metadata["job_token_breakdown"] = {
        "1_input_cached": cached_input,
        "2_input_uncached": uncached_input,
        "3_total_billed": api_total_billed,
        "4_output_candidates": api_output,
        "5_hidden_processing": processing_tokens
    }
    return api_total_billed, api_total_input, api_output

# response output helper: parse output and json output from the API call (helper)
def process_and_save_candidates(run_id: str, batch_id: str, job_id: str, response, output_file: Path,
                               full_metadata: Dict[str,Any], logger) -> int:
    """
    response processing layer 3: core logic. Loops candidates, parses JSON
    enriches data, and saves to disk.
    
    Returns the count of successfully saved questions.
    """
    # counter for candidates
    total_saved = 0

    for i, candidate in enumerate(response.candidates):
        try:
            # Safety check for empty content parts
            if not candidate.content.parts:
                logger.warning("[job id: %s] Candidate %s has no content parts.", job_id, i)
                continue
            # Extract text from this specific candidate
            # (Gemini structure: candidate -> content -> parts -> text)    
            raw_candidate_text = candidate.content.parts[0].text

            # Use the helper function defined earlier in your script
            parsed_questions = extract_json_from_response(raw_candidate_text)

            if parsed_questions:
                with open(output_file, 'a', encoding='utf-8') as f:
                    # write question data with full metadata to file (make sure they are standalone)
                    for q_idx, question_data in enumerate(parsed_questions):
                        # 0. Generate Deterministic ID
                        # Format: {run_id}_{job_id}_{candidate_index}_{question_index}
                        # Example: "run20251224_x9z_batch_MCQ_Generation_a7b2_job_e5f6_0_0" <- long for data quality tracking
                        unique_id = f"{run_id}_{batch_id}_{job_id}_{i}_{q_idx}"
                        question_data['question_id'] = unique_id
                        # 1. Identity: track exactly where the question came from
                        question_data['candidate_index'] = i
                        question_data['question_index'] = q_idx
                        # 2. Context: inject the full run/job metadata
                        question_data['batch_generation_info'] = full_metadata
                        # 3. Persistence: Write to JSONL
                        f.write(json.dumps(question_data) + "\n")

                total_saved += len(parsed_questions)

            else:
                # Log the source file name if possible for debugging
                source_file = full_metadata.get('source_files', 'Unknown')
                logger.warning("❌ [job id: %s] JSON extraction failed for Candidate %s in %s",
                               job_id, i, source_file)

        # Specific error handling
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            logger.error("[job id: %s] Data Error processing Candidate %s: %s", job_id, i, e)
            continue
        except OSError as e:
            logger.error("[job id: %s] File System Error saving Candidate %s: %s", job_id, i, e)
            continue
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("[job id: %s] 💥 Critical Unexpected Error on Candidate %s: %s",
                         job_id, i, e)
            continue

    return total_saved

# Process and save questions from candidates as individual entries in jsonl file
@task
def parse_and_save(run_id:str, batch_id: str, job_id: str, response, output_file: Path, full_metadata: Dict[str,Any], 
                   template_token_count: int) -> Tuple[int, int, int, int]:
    """
    Orchestrator task for the ETL processing of model response. it uses helper methods to:
    1. Checks safety (forensics) - was API call suceessful or blocked
    2. Calculates token counts (accounting) for the job (all candidates) 
    3. Parses individual questions_data dict and saves the data as jsonl (core logic)
    
    Returns: Tuple of (saved_count, input_tokens, output_tokens), where:
    saved_count : number of questions generated and saved
    input_tokens: total input tokens for the job (prompt template + chapters)
    output_tokens: output token counts (single candidate if run has mulitple)
    """
    logger = get_run_logger()

    # Step 1: forensics
    is_safe = check_safety_and_feedback(response, full_metadata, job_id, logger)

    # initialize variablest
    saved_count, t_in, t_out = 0, 0, 0
    
    # Step 2: accounting (token counts from helper)
    total_billed, t_in, t_out = calculate_token_metrics(response, full_metadata, template_token_count)
    
    # check if api call was blocked before proceeding (SAFETY, or other reason response is empty) 
    if not is_safe:
        # Return 0 saved, but still track the cost
        return 0, total_billed, t_in, t_out

    # Step 3: core logic
    saved_count = process_and_save_candidates(run_id, batch_id, job_id, response, output_file, full_metadata, logger)

    if saved_count > 0:
        logger.info("✅ [job id: %s] Saved %s questions. Total tokens: %s",
                    job_id, saved_count, total_billed)
    
    else: # explicitly log the zero question failure event + the cost incurred 
          # (call not blocked, but no questions to parse e.g. missing '[' delimiters], 
          # MAX_TOKENS hit in middle of first question, etc)
        logger.warning("⚠️ [job id: %s] 0 questions saved. Tokens wasted: %s", 
                       job_id, total_billed)    

    return saved_count, total_billed, t_in, t_out

# placeholder for cost esmtimate helper if needed for later dataset expansion
def estimate_run_cost(total_input: int, total_output: int, models_used: list) -> float:  
    """
    Placeholder for cost estimation. 
    Currently returns $0.00 for Free Tier runs.
    
    Future Logic (Pay-As-You-Go): UPDATE to most recent costs
    - Pro: ~$3.50 / 1M input, ~$10.50 / 1M output
    - Flash: ~$0.35 / 1M input, ~$1.05 / 1M output
    """
    # Silence linter warnings for unused args (placeholder logic)
    _ = (total_input, total_output, models_used)
    # TODO: update if Paid Tier needed to expand dataset in later iterations
    # PRICING = {
    #     "PRO": {"input": xx.xx, "output": xx},
    #     "FLASH": {"input": xx, "output": xxx}
    # }
    # ... calculation logic ...

    return 0.0

@task
def save_run_completion(run_id: str, run_stats: dict) -> None:
    """
    Saves the final metrics of the run to a JSON file.
    This acts as the 'Receipt' proving the run finished successfully.
    """
    # Save in the same logs folder
    runs_dir = RUNS_DIR

    completion_data = {
        "run_id": run_id,
        "status": "SUCCESS",
        "timestamp_end": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "total_questions": run_stats['total_questions'],
            "total_tokens": run_stats['total_billed'],
            "input_tokens": run_stats.get('total_input', 0),
            "output_tokens": run_stats.get('total_output', 0),
            "chapters_processed": run_stats.get('chapters_processed', 0)
        },
        "models_used": list(run_stats.get('models_used', []))
    }

    file_path = runs_dir / f"run_result_{run_id}.json"

    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(completion_data, f, indent=2)

    logger = get_run_logger()
    logger.info("🏁 Run Completion saved to: %s", file_path)

# generate a completion report
@task
def create_run_report(run_id: str, run_timestamp: str, run_stats: dict, output_root: Path):
    """
    Generates a Markdown summary of the run and publishes it to the Prefect UI.
    """
    # 1. Get (placeholder) Cost
    # add step for cost estimation when needed

    # 2. Format Model List
    models_str = ", ".join(run_stats['models_used'])

    # 3. Build the Markdown Report
    report = f"""
# 🧙‍♂️ Harry Potter Trivia: Question Generation Report

| **Global Metric** | **Value** |
|:---|---:|
| **Run ID** | `{run_id}` |
| **Date** | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} |
| **Runtime** | {run_timestamp} |
| **Chapters Processed** | {run_stats.get('chapters_processed', 0)} |
| **Models Active** | {models_str} |

## 📊 Result Metrics

| Resource | Count |
|:---|---:|
| **Total Input Tokens** | {run_stats['total_input']:,} |
| **Total Output Tokens** | {run_stats['total_output']:,} |
| **Total Billed** | **{run_stats['total_billed']:,}** |
| **Questions Created** | **{run_stats['total_questions']}** |

## 📂 Output Artifacts
Files are saved in: `{output_root}/{run_id}/`
"""
    # 4.1. Create Prefect Artificat for dashboard
    create_markdown_artifact(
        key=f"report-{run_id}",
        markdown=report,
        description=f"Run Summary: {run_id}"
    )

    # 4.2. Also publish report to console (Teriminal or not) using Rich
    console = Console()
    console.print("\n") # Add some spacing
    console.print(Markdown(report))
    console.print("\n")

    # 5. Log to console
    logger = get_run_logger()
    logger.info("📝 Artifact created. Total Questions: %s", run_stats['total_questions'])

## ORCHESTRATOR

@flow(name="Harry Potter Question Generation")
def generate_questions_pipeline(target_books: List[Book],
                                target_chapters: Optional[List[int]] = None,
                                tasks_to_run: Optional[List[str]] = None,
                                chapter_limit: Optional[int] = None,
                                batch_size: int =2):
    """
   Orchestrates the full generation lifecycle: Initialization -> Manifest -> Batched Execution -> Reporting.

    Args:
        target_books (List[Book]): The specific books to process.
        target_chapters (List[int], optional): Specific chapter numbers to target (e.g., `[1, 5]`).
        tasks_to_run (List[str], optional): Specific strategies to execute (e.g., `["MCQ_Generation"]`). 
            Defaults to ALL strategies if None.
        chapter_limit (int, optional): Caps the number of chapters processed (useful for pilots).
        batch_size (int, default=2): Files processed per API call. 
            * **Default (2):** Optimized for full chapters (balances context vs. output limits).
            * **Higher (10+):** Recommended for short thematic excerpts.

    Examples:
        >>> # 1. Standard Full Run
        >>> generate_questions_pipeline(target_books=[Book.BOOK_3])
        >>> # 2. Surgical Canary Run (Specific Chapters)
        >>> generate_questions_pipeline(target_books=[Book.BOOK_3], target_chapters=[15, 16])
        >>> # 3. Thematic Run (High Throughput)
        >>> generate_questions_pipeline(target_books=[Book.THEME_DOBBY], batch_size=10)
    """
    ## A. INITIALIZATION (RUN LEVEL)
    # A.1: generate identifiers
    pipeline_id = PIPELINE_ID
    run_id = f"run{datetime.now().strftime('%Y%m%d')}_{short_uuid()}"
    run_timestamp = datetime.now(timezone.utc).isoformat()

    # A.2: Deterimine the specific run strategy (if filtered):
    active_strategy = filter_strategy(GENERATION_STRATEGY, tasks_to_run)

    # A.3.1: Configure the pipeline Prefect logger filehandler
    log_path = configure_file_logging(run_id)
    # A.3.2: Initialize logger and print initiation messages
    base_logger = get_run_logger()
    # Add run_id as 'Trace' id to logger messages
    extra_context = {'run_id': run_id}  
    logger = logging.LoggerAdapter(base_logger, extra_context)
    logger.info("🚀 Starting Pipeline: %s", run_id)
    logger.info("Prefects UI Logs mirroring to: %s", log_path)

    # A.4: configure the pipeline API
    configure_api(CONFIG_PATH)
    
    # A.5: distinguish between a book vs. thematic run
    target_folder = determine_target_folder(target_books)
    if "themes" in target_folder:
        logger.info("Thematic Run detected. Switching source to: %s", target_folder)

    # A.6: Retrieve chapter files and run scope
    # A.6.1: Retrieve list of required run chapter paths
    chapter_file_paths = get_chapters(target_books,
                                      target_book_folder=target_folder,
                                      chapter_filter=target_chapters,
                                      limit=chapter_limit)
    # A.6.2: Check if the run is on full_book or partial_pilot 
    run_scope =  get_run_scope(chapter_limit, target_chapters)
    # A.6.3: log special case if chapter limits applied (e.g. demo, troubleshooting)
    if chapter_limit:
        logger.warning("🛑 Processing Cap Applied: Limiting execution to %s chapters.",
                       chapter_limit)

    # A.7: Create and save the run manifest (= plan for this run)
    save_run_manifest(run_id, 
                      pipeline_id, 
                      active_strategy,
                      target_books,
                      chapter_file_paths,
                      run_timestamp,
                      run_scope)
    
    # A.8: Initialize the run_stats dict (tracking batches, job metadata)
    run_stats = init_run_stats()

    ## B. GENERATION STRATEGY LOOP (BATCH LEVEL):
    #  B.1: Loop through the selected question types from active strategy:
    for config in active_strategy:
        # create batch identifiers
        task_name = config.get('task_name', 'UnknownTask')
        # safety: ensure the name is URL/ID friendly (no spaces or weird chars)
        safe_task_name = task_name.replace(" ", "_").strip()
        batch_id = f"batch_{safe_task_name}_{short_uuid()}"
        logger.info("\n--- Starting Strategy: %s ---", task_name)
        
        # input token count for prompt template without formatting
        template_token_count = measure_template_tokens(config['model_name'],
                                                           config['prompt_file'])
        # update run_stats dict
        run_stats["models_used"].add(config['model_name'])
    
        # Initialize count for consecutive failures (circuit breaker)
        consecutive_failures = 0
        
        ## C. CHAPTER LOOP (JOB LEVEL)
        # Loop through batch_size number of chapters per loop (default = 2)
        for chapter_batch in chunk_list(chapter_file_paths, batch_size):
                    
            # C.1: Safety check: abort run if consecutive failures exceed limit
            if consecutive_failures >= MAX_FAILURES:
                logger.error("🚨 Aborting %s due to %s consecutive failures.",
                             task_name, MAX_FAILURES)
                break
            
            # C.2: Initialize 
            job_id = f"job_{short_uuid()}"
            # Extract names for metadata (since chapter_batch is a list of Paths)
            batch_names = [p.stem for p in chapter_batch]
            tokens_in = 0
            tokens_out = 0
            
            # C.3: prepare prompt (fill in template)
            final_prompt = prepare_prompt(chapter_batch,config['prompt_file'])
            
            try:
                # C.4: Make the API call
                response = make_api_call(final_prompt, config)
                
                # C.5: generate the full meta_data dict for job
                full_metadata = create_strategy_batch_metadata(run_id, batch_id, 
                                                               job_id, run_timestamp,
                                                               config, batch_names)
                
                # C.6: save the response into a jsonl
                # C.6.1: construct output filename
                first_chap = chapter_batch[0].stem  # chapter ref in filename
                output_file = OUTPUT_DIR / f"{config['file_prefix']}_{first_chap}_{run_id}.jsonl"
                # C.6.2: parse and save as jsonl with Task
                q_count, total_tokens, tokens_in, tokens_out = parse_and_save(run_id, batch_id,
                    job_id, response, output_file, full_metadata, template_token_count)
                
                # C.7: Assess if run was a failure (no questions generated)
                # if successful update run_stats else update failure counter
                if  q_count> 0:
                    consecutive_failures = 0
                    run_stats["total_questions"] += q_count
                    run_stats["total_input"] += tokens_in
                    run_stats["total_output"] += tokens_out
                    run_stats["total_billed"] += (total_tokens)
                    # counter for actual chapters processed (increment by batch len)
                    run_stats["chapters_processed"] += len(chapter_batch) 
                else:
                    consecutive_failures += 1

            except Exception as e:  # pylint: disable=broad-exception-caught
                consecutive_failures += 1
                # even a failed run can have billed token counts
                run_stats["total_billed"] += (tokens_in + tokens_out)
                logger.error("Error on %s: %s", first_chap, e)
                continue

            # C.8: pacing (safe time delay for RPM limits)
            delay = config.get('rate_limit_delay', 10)
            time.sleep(delay)
    
    ## D: WRAP-UP
    # D.1: list of model used converted to json compatible format (set -> list)
    run_stats["models_used"] = list(run_stats["models_used"])
    
    # D.2: save log run and creates a summary report for Prefect UI or Terminal
    create_run_report(run_id, run_timestamp, run_stats, OUTPUT_DIR)
    # save actual metrics of run for traceability (run "reciept")
    save_run_completion(run_id, run_stats)
    # completion update
    logger.info("🏁 Pipeline Finished: %s",run_id)

if __name__ == "__main__":
    # 1. Setup the Argument Parser
    parser = argparse.ArgumentParser(description="Run the Harry Potter Generation Pipeline.")

    # 2. Add the '--tasks' argument
    # For selective GENERATION_STRATEGY runs insted of full execution
    parser.add_argument(
        "--tasks", 
        nargs="+", # Accepts 1 or more values
        help="List of specific tasks to run (e.g. 'MCQ_Generation'). Default is ALL.",
        default=None
    )
    # limit number of chapters (e.g 1 for demo mode)
    parser.add_argument("--limit", type=int, help="Limit number of chapters (for testing).")

    # select a specific book(s) to use
    parser.add_argument(
        "--books", 
        nargs="+", 
        choices=["BOOK_3", "BOOK_4", "BOOK_7"], # Constrain inputs
        required=True, 
        help="Specific books to process. REQUIRED (e.g. --books BOOK_3)."
    )

    #Select specific chapters
    parser.add_argument(
        "--chapters",
        nargs="+",
        type=int,
        help="Specific chapter numbers to run (e.g. 1 5 10). Default are all chapters in book.",
        default=None
    )
    
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=2,
        help="Chapters per API call. Default: 2 (Proven). Max Rec: 4."
    )

    # 3. Parse arguments
    args = parser.parse_args()
    # Convert string args to Enum objects:  "BOOK_3" -> Book.BOOK_3
    target_book_enums = [getattr(Book, b) for b in args.books]

    try:
        # 4. Run the Flow
        generate_questions_pipeline(target_books=target_book_enums,
                                    target_chapters=args.chapters,
                                    tasks_to_run=args.tasks,
                                    chapter_limit=args.limit,
                                    batch_size=args.batch_size)
    except KeyboardInterrupt:
        # This catches Ctrl+C
        print("\n🛑 User aborted execution via KeyboardInterrupt.")
        # TODO Consider: can call a cleanup function e.g., save_partial_results() 
        logger = logging.getLogger("prefect")
        logger.error("\n🛑 Pipeline execution aborted by user (KeyboardInterrupt).")
        sys.exit(130) # Standard exit code for Script Terminated by Ctrl-C
    except Exception as e:  # pylint: disable=broad-exception-caught
        # This catches crashes
        logger = logging.getLogger("prefect")
        logger.error(f"\n💥 Pipeline crashed with critical error: {e}")
        sys.exit(1)    
