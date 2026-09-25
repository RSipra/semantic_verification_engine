"""
Project: SVE (ref implementation: Harry Potter Trivia)
Automated Question Generation Pipeline using PREFECT.
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
Date: November 2025 (updated Jul 2026)

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
## TODO: preserve raw LLM response on quarantine

**Problem**
Quarantine currently records the failure reason but not the raw LLM response.
When a record fails to construct, the jsonl checkpoint is dumped from the DTO —
so a failed record leaves no trace of what the LLM actually returned. Diagnosing
a bad pass means seeing "3 records quarantined, missing `hint`" with no way to
inspect the response that caused it.

**Fix**
On quarantine write, include the raw response text for the failing record
alongside the existing fields:

- `syn_id`
- `batch_key` — (book, chapter, type, chunk)
- `reason` — parse failure / missing syn_id / construction failure + field
- `raw_response` — the LLM output for this record, unmodified
- `pass` — lexical / semantic / generation
- `timestamp`

Successes don't need this; the DTO dump is faithful for those. Quarantine +
checkpoint together are the complete picture.

**Scope**
- [ ] Enrichment pipeline — build in from the start, quarantine write is new code
- [ ] Generation pipeline — confirm current behaviour, close the same gap if raw
      response is discarded on failure

**Notes**
Where the record failed to parse at all (no valid JSON), `raw_response` may be
the whole batch response rather than a per-record slice. Acceptable — record
which it is in `reason`.

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
from google.api_core import retry as api_retry
from google.api_core import exceptions as core_exceptions
from google.generativeai.types.helper_types import RequestOptionsDict
from prefect import flow, task, get_run_logger #pipeline orchestrator
from prefect.artifacts import create_markdown_artifact
from rich.console import Console
from rich.markdown import Markdown

# IMPORT PROJECT CONFIGURATION
# Using the "Src Layout" (pip install -e .)
from core.constants import Book, QuestionSource
from core.models import DraftQuestion
from scripts.pipelines.generate_questions.prompts.pipeline_config import GENERATION_STRATEGY, GEN_STRATEGY_VERSION
import notebook_support.notebook_config as nb_cfg

## CONSTANTS

# Main Paths
PROMPTS_DIR = nb_cfg.PROMPTS_DIR
OUTPUT_DIR = nb_cfg.GENERATED_QUESTIONS_DIR     # generated question dtos as jsonls 
CONFIG_PATH = nb_cfg.PROJECT_ROOT / 'config.env'

# Reporting Paths (centralized)
PIPELINE_LOGS_ROOT = nb_cfg.PIPELINE_LOGS_ROOT  # parent dir
MANIFESTS_DIR = nb_cfg.MANIFESTS_DIR            # run manifests (run plans before execution)
RUNS_DIR = nb_cfg.RUNS_DIR                      # run receipts + call logs (after execution)
LOGS_DIR = nb_cfg.LOGS_DIR                      # Prefect file-handler output
# safety check: ensure directories that will be written to exist immediately
for d in [OUTPUT_DIR, MANIFESTS_DIR, RUNS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ARTIFACT NAMING
# standardized unique identifier for this question_generation script with version
PIPELINE_ID = "pipe_q_gen_v00"

# Standard suffixes for run artifacts (see build_run_artifact_path)
MANIFEST = "manifest.json"
CALLS    = "calls.jsonl"
RECEIPT  = "receipt.json"
QUARANTINE = "quarantine.jsonl"

LLM_PASS_GEN = 'generation'    

# Pipeline settings (circuit breaker limit - how many failed runs before aborting pipeline)
MAX_FAILURES = 5
# SDK 500 retry policy: same as SDK default but with 30s budget instead of 600s
# See the make_api_call docstring for why.
SDK_RETRY = api_retry.Retry(
    initial=1.0, maximum=10.0, multiplier=1.3,
    timeout=15.0,  
    predicate=api_retry.if_exception_type(core_exceptions.ServiceUnavailable),
)
REQUEST_OPTIONS: RequestOptionsDict ={"retry": SDK_RETRY, "timeout": 60}

# GENERATION_STRATEGY: Predefined models for each question type (model-per-type based 
# on experimentation) imported from src/ds_utils/ds_constants

class RunIDFilter(logging.Filter):
    """Injects a default run_id on any log record missing one, so the
    file formatter's %(run_id)s never KeyErrors on Prefect's own logs."""
    def __init__(self, run_id: str):
        super().__init__()
        self.run_id = run_id
    def filter(self, record):
        if not hasattr(record, "run_id"):
            record.run_id = self.run_id
        return True

## TASKS AND HELPERS

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

def build_run_artifact_path(directory: Path, run_id: str, llm_pass: str, kind: str) -> Path:
    """
    Build the standard path for a run artifact: `{run_id}_{llm_pass}_{kind}`.

    Every artifact a pass produces starts with the same stem, so one run's
    manifest, calls log, receipt and checkpoints sort together, and all passes
    of a run are found by globbing the run_id. Both pipelines call this, so the
    convention cannot drift between them.
    
    Callers pass their own `llm_pass` — shared helpers must never hardcode one,
    or a pass will write over another's artifacts
    
    Note: not used for generation's question checkpoints. Those are keyed by
    question type and chapter — three question types run inside the single
    generation pass — so `{run_id}_generation` does not distinguish them, and
    they are named directly at the call site.

    Args:
        directory: where it lives — RUNS_DIR, MANIFESTS_DIR, OUTPUT_DIR.
        run_id: shared by every artifact of one end-to-end run.
        llm_pass: "generation", "lex_enrichment", "semantic_enrichment".
        kind: the suffix — a constant (MANIFEST, CALLS, RECEIPT, QUARANTINE)
            or a computed batch identity, e.g. "FR_batch0.jsonl"
    """
    return directory / f"{run_id}_{llm_pass}_{kind}"

def append_jsonl(entry: dict, file_path: Path) -> None:
    """
    Append one record dict to a jsonl file, creating it if absent.

    Used for artifacts that accumulate during a run (call entries, quarantine)
    so that a run interrupted partway still leaves what it produced
    on disk.
    
    For DTO batches written whole, see `write_jsonl_checkpoint`.
    """
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

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
    # Path setup: (run-scoped) the handler attaches to the process-wide
    # prefect logger, so one file captures every pass in this process
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
    formatter = logging.Formatter(
        '%(asctime)s | TRACE:%(run_id)s | %(levelname)s | %(message)s'
    )
    fh.setFormatter(formatter)

    # Filter guarantees run_id exists on every record
    fh.addFilter(RunIDFilter(run_id))

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
        chapter_limit: Maximum number of chapters to return.

    Returns:
        List[Path]: A list of pathlib.Path objects for every matching text file,
                    sorted alphanumerically to ensure deterministic processing order.
    """
    books_dir = nb_cfg.DATA_DIR / target_book_folder
    # convert Enums to a tuple of strings for startswith()
    prefixes = tuple(book.value for book in target_books)

    # find all the chapter files by book name (prefix in the filename)
    relevant_file_paths = [p for p in books_dir.iterdir() if p.name.startswith(prefixes)]
    selected_chapter_paths = relevant_file_paths  # default to all if no filter applied

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
            except ValueError: # if a single file fails
                get_run_logger().warning(
                    "⚠️ Skipping file with non-standard name (can't parse chapter number): %s", p.name)
                continue
        if not filtered_files:  # incase no chapters matched the filter, log a warning
            raise ValueError(
                f"No chapters matched the filter {chapter_filter} in {target_books}. "
                f"Check chapter numbers and naming convention.")
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
                      llm_pass: str, target_books: List[Book], chapters: list, 
                      run_timestamp: str, run_scope: str) -> None:
    """
    Saves the execution plan (*recipe*) before execution starts. This is to help distinguish 
    between attempted runs (e.g aborted, crashed) vs. successful runs (with full reporting, 
    artifacts)
    
    Full run-level traceability / reproducibility: 
        - run_manifest *here* (what was planned, written before execution)
        - questions jsonl (the DTOs produced, one record per line)
        - calls jsonl (one accounting line per API call)
        - run_receipt (summary of one LLM pass: settings, totals,
            status)
    
    Args:
        run_id: The unique UUID for this pipeline execution.
        pipeline_id: The versioned identifier for this script logic (e.g., 'pipe_q_gen_v0').
        active_strategy: The list of active (filtered if applicable) generation configs 
        (models, prompts) to be executed.
        target_books: The specific list of Book enums targeted in this run.
        chapters: The specific list of chapters file paths selected for this run.
    """
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
    filename = build_run_artifact_path(MANIFESTS_DIR, run_id, llm_pass, MANIFEST)
    with open(filename, 'w', encoding='utf-8') as f:
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
        raise ValueError(f"Prompt template file is empty: {prompt_path.name}")
    #2. if the prompt template doesn't have a placeholder for the chapters (source text)    
    if "{source_text}" not in prompt_template:
        raise ValueError("Prompt template is missing the required '{source_text}' placeholder.")
    #3. if the prompt template doesn't have a placeholder for the source info (references)    
    if "{valid_source_list}" not in prompt_template:
        raise ValueError(
            f"Prompt template {prompt_path.name} is missing the required '{{valid_source_list}}' placeholder.")

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
@task(retries=3, retry_delay_seconds=[60, 120, 300])
def make_api_call(final_prompt:str, config: dict):
    """
    Calls Gemini with built-in retries and specific generation parameters.
    
    Retry policy (2026-09-24): 
    --------------------------
    google-api-core's default retry on generate_content(503 only,
    deadline=600s, backoff capped at 10s, full jitter) makes ~120 requests
    per call during a 503 burst (~12 RPM, matching the 13 RPM observed
    on the dashboard). Stacked under Prefect retries, a burst used 422/500 RPD.
    Capped at timeout=15s: measured 8 attempts in 13.3s via probe_api --offline.
    Worst case with Prefect retries=3 is ~32 requests per task.
    Do not raise either without rerunning the probe.
    
    Args:
        final_prompt: The finalized prompt string
        config: A dictionary containing 'model_name', 'temperature', etc.
    
    # TODO (caching): chapter-major loop + chapter-first prompts would make chapter
    # text cacheable across question types. Tracer: each chapter pair is sent once
    # per type with an identical payload (11–18k tokens). Templates alone (768–1,684)
    # are all below the implicit-caching minimum, so template caching is not viable.
    # Ceiling: (k-1)/k of chapter sends cached at ~90% discount (k = question types;
    # 67% at k=3). Revisit when: moving off free tier, or full-corpus runs become
    # frequent. Requires a prompt experiment first — instruction/source ordering
    # affects output quality (see ex_primacy_bias).
    # Evidence: 1_input_template vs 3_input_cached_actual in run receipts.   
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
        response_mime_type="application/json"
    )
  
    # 3. Call API
    try:
        response = model.generate_content(
            final_prompt,
            generation_config=gen_config,
            request_options= REQUEST_OPTIONS)
        return response
    except Exception as e:
        logger.error("API Call failed for %s: %s", model_name, e)
        raise e

# helper to parse the json output from the API response object
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
            "pipeline_name" : PIPELINE_ID,
            "pipeline_run_id": pipeline_run_id,     # Run: [parent] full script run
            "batch_id": batch_id,                   # Strategy: [group] question type batch 
            "job_id": job_id                        # Job: [child] specific API call
        },
        "timestamp": run_timestamp,                 # pipeline run timestamp
        # context
        "generation_strategy_version": GEN_STRATEGY_VERSION,  # static config version
        "source_files": ", ".join(source_filenames),   # job level
        "question_type": strategy.get('file_prefix'),
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
def check_safety_and_feedback(response, full_metadata: Dict[str, Any], job_id: str, logger_obj) -> bool:
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
        logger_obj.error("⛔ [job id: %s] Safety Block triggered. Feedback: %s", job_id, prompt_feedback)
        return False 

    # 2. Empty/Malformed Response Check
    if not hasattr(response, 'candidates') or not response.candidates:
        logger_obj.error("[job id: %s] No candidates found in response object.", job_id)
        return False

    return True

# response output processing helper: calculate token counts
def calculate_token_metrics(response, 
                            template_token_count: int) -> dict:
    """
    Response processing layer 2: accounting. Records a granular token breakdown
    for one LLM call in `full_metadata["job_token_breakdown"]` and returns the
    headline counts. Shared by generation and enrichment passes.

    Input tokens are split into two parts, because every prompt in this pipeline
    is a fixed template with variable content injected at the end:
      - template: the prompt template before injection, identical across calls
        in a pass (measured locally, passed in as `template_token_count`)
      - payload:  the injected content — chapter text for generation, the
        question batch for enrichment (derived: total input - template)

    1. Why both template and actual-cached counts are recorded:
    
    The caching strategy is not yet decided, and these fields are the evidence
    for it. `1_input_template` is the ceiling — tokens that *could* be cached,
    since every call in a pass shares the same template prefix.
    `3_input_cached_actual` is what the provider *did* cache and bill at the
    reduced rate. Tracer: all templates are below the implicit-caching minimum,
    so expect ~0 until prompt structure changes (see caching TODO on the
    generation loop). Reports cache hits from implicit or explicit caching
    alike, so this accounting holds if explicit caching is adopted.
    
    2. Why thinking and residual are separated: 
    
    `6_thinking_actual` is the API's chain-of-thought count, billed at the
    output rate. `7_other_processing` is the residual — billed minus input,
    visible output and thinking — so the breakdown sums to the total. Expected
    ~0; a non-zero value means something else is being billed (e.g. tool-use
    prompt tokens). Tracer: hidden tokens were 20% of generation and ~40% of
    enrichment totals — the largest controllable cost (see thinking_level TODO).

    NB: experiment logs (experiments/*.yaml) use input_cached / input_uncached
    for the same template / payload split. Not provider caching.

    Args:
        response: Raw API response; read via `response.usage_metadata`.
        full_metadata: Metadata dict for this call, updated in place.
        template_token_count: Tokens in the prompt template before injection.

    Returns:
        (total_billed, total_input, output) as reported by the API.

    Breakdown keys written:
        1_input_template:       template_token_count
        2_input_payload:        total input - template (floored at 0)
        3_input_cached_actual:  cached_content_token_count from the API
        4_output_candidates:    output tokens
        5_total_billed:         total_token_count from the API
        6_thinking_actual:      thoughts_token_count from the API
        7_other_processing:     billed - (input + output + thinking), e.g. other processing tokens
    """
    # Extract raw numbers from the API
    usage = getattr(response, 'usage_metadata', None)
    api_total_input = getattr(usage, 'prompt_token_count', 0) or 0
    api_output = getattr(usage, 'candidates_token_count', 0) or 0
    api_cached = getattr(usage, 'cached_content_token_count', 0) or 0
    api_thinking     = getattr(usage, 'thoughts_token_count', 0) or 0
    api_total_billed = getattr(usage, 'total_token_count', 0) or 0 # total tokens

    # Calculate granular custom metrics
    # a. prompt template w/o formatting 
    input_template = template_token_count
    # b.  - Generation pass: chapter_text & source_info tokens
    #     - Enrichment pass: question batch tokens    
    input_payload = max(0, api_total_input - input_template)
    # c. hidden processing tokens (billed but not in input/output)  
    other_processing_tokens = api_total_billed - (api_total_input + api_output + api_thinking)

    # return breakdown as dict
    return {
        "1_input_template": input_template,
        "2_input_payload": input_payload,
        "3_input_cached_actual": api_cached,
        "4_output_candidates": api_output,
        "5_total_billed": api_total_billed,
        "6_thinking_actual": api_thinking,
        "7_other_processing": other_processing_tokens,
    }

# Convert LLM response candidates into DraftQuestion objects
# NOTE: DraftQuestion is generated at runtime (see ADR-P2-023); Pylance can't resolve
# a variable in a type expression, annotation is documentation only.
def convert_question_to_dto(question_data: Dict[str, Any]) -> DraftQuestion:  # type: ignore
    """
    Converts a raw question dictionary into a DraftQuestion DTO.
    """
    return DraftQuestion(**question_data)

# response output helper: parse output and json output from the API call (helper)
def process_and_save_candidates(run_id: str, batch_id: str, job_id: str, response, output_file: Path,
                               full_metadata: Dict[str,Any], logger) -> Tuple[int, List[DraftQuestion]]:  # type: ignore
    """
    response processing layer 3: core logic. Loops candidates, parses JSON
    enriches data, and saves to disk.
    
    Returns the count of successfully saved questions and the list of draft questions.
    """
    # counter for candidates
    total_saved = 0
    draft_questions = []

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
                        # Format: {run_id}_{batch_id}_{job_id}_{candidate_index}_{question_index}
                        # Example: "run20251224_x9z_batch_MCQ_Generation_a7b2_job_e5f6_0_0" <- long for data quality tracking
                        unique_id = f"{run_id}_{batch_id}_{job_id}_{i}_{q_idx}"
                        
                        # 1. Identity: track exactly where the question came from
                        question_data['syn_id'] = unique_id
                        question_data['question_source'] = QuestionSource.SYNTHETIC.value
                        
                        # 2. Context: inject the full run/job metadata
                        question_data['generation_model'] = full_metadata.get('model_name')
                        question_data['timestamp'] = full_metadata.get('timestamp')
                        question_data['generation_prompt_version'] = full_metadata.get('prompt_template')
                        question_data['generation_pipeline_id'] = full_metadata['identifiers'].get('pipeline_name')
                        question_data['generation_strategy_version'] = full_metadata.get('generation_strategy_version')
                        
                        # 3. Persistence: Write to JSONL
                        f.write(json.dumps(question_data) + "\n")
                        
                        # 4. Create DTO
                        draft_question = convert_question_to_dto(question_data)
                        draft_questions.append(draft_question)

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

    return total_saved, draft_questions

# Process and save questions from candidates as individual entries in jsonl file
@task
def parse_and_save(run_id, batch_id, job_id, response, output_file: Path,
                   calls_file: Path, full_metadata: Dict[str, Any],
                   chapter_count: int,
                   template_token_count: int) -> Tuple[Dict[str, Any], List[DraftQuestion]]: # type: ignore
    """
    Orchestrator task for the ETL processing of model response. it uses helper methods to:
    1. Checks safety (forensics) - was API call suceessful or blocked
    2. Calculates token counts (accounting) for the job (all candidates) 
    3. Parses individual questions_data dict and saves the data as jsonl (core logic)
    
    Full run-level traceability / reproducibility: 
    - run_manifest  (what was planned, written before execution)
    - questions jsonl *here* (the DTOs produced, one record per line)
    - calls jsonl *here* (one accounting line per API call)
    - run_receipt (summary of one LLM pass: settings, totals,
        status)
    
    Returns: Tuple of (call_entry dict, list of DraftQuestion DTOs). 
    call_entry is one accounting line for this API call, appended to the run's
    calls jsonl before returning. Blocked or empty calls are recorded too (to 
    capture tokens that are still billed with these calls).
    Fields:
        call_id, batch_id: identifiers for this call and its strategy batch
        question_type, model: what was asked for and which model answered
        output_file: name of the jsonl this call's questions were written to
        questions_saved: how many questions were parsed and saved (0 if blocked)
        tokens: the seven-key breakdown from calculate_token_metrics
        quarantined: None — generation does not yet track failure modes
    """
    logger = get_run_logger()

    # Step 1: forensics
    is_safe = check_safety_and_feedback(response, full_metadata, job_id, logger)

    # Step 2: accounting (token counts from helper)
    token_breakdown = calculate_token_metrics(response, template_token_count)
    
    # intialize call metadata including token counts (even if no questions saved)
    call_entry = {
        "call_id": job_id,
        "batch_id": batch_id,
        "question_type": full_metadata.get("question_type"),
        "model": full_metadata.get("model_name"),
        "chapter_count": chapter_count,          
        "prompt_version": full_metadata.get("prompt_template"),
        "output_file": output_file.name,
        "questions_saved": 0,
        "tokens": token_breakdown,
        "quarantined": None,
    }

    # check if api call was blocked before proceeding (SAFETY, or other reason response is empty) 
    if not is_safe:
        # Return 0 saved, but still track the cost
        append_jsonl(call_entry, calls_file)
        return call_entry, []

    # Step 3: core logic (save questions.jsonl file)
    saved_count, draft_questions = process_and_save_candidates(run_id, batch_id, job_id, 
                                              response, output_file, full_metadata, logger)

    if saved_count > 0:
        logger.info("✅ [job id: %s] Saved %s questions. Total tokens: %s",
                    job_id, saved_count, call_entry['tokens']['5_total_billed'])
        # update with question count for the call
        call_entry["questions_saved"] = saved_count

    else: # explicitly log the zero question failure event + the cost incurred 
          # (call not blocked, but no questions to parse e.g. missing '[' delimiters], 
          # MAX_TOKENS hit in middle of first question, etc)
        logger.warning("⚠️ [job id: %s] 0 questions saved. Tokens wasted: %s",
                       job_id, call_entry['tokens']['5_total_billed'])

    # Step 4: write call entry to file (call.jsonl)
    append_jsonl(call_entry, calls_file)

    return call_entry, draft_questions

# placeholder for cost esmtimate helper if needed for later dataset expansion
def estimate_run_cost(run_receipt: Path) -> float:  
    """
    Placeholder for cost estimation. 
    Currently returns $0.00 for Free Tier runs.
    
    Reads the receipt's token totals rather than taking counts, so cost is
    computed from what was actually recorded. Thinking tokens bill at the
    output rate, and cached input bills at a reduced rate — both are in the
    breakdown, so the estimate can reflect them when pricing is filled in.
    
    Future Logic (Pay-As-You-Go): UPDATE to most recent costs
    - Pro: ~$3.50 / 1M input, ~$10.50 / 1M output
    - Flash: ~$0.35 / 1M input, ~$1.05 / 1M output
    """
    # Silence linter warnings for unused args (placeholder logic)
    # TODO:(cost): placeholder while on the free tier. When pricing is needed:
    #   - compute from the receipt's token breakdown, not raw in/out counts —
    #     thinking tokens (6_thinking_actual) bill at the output rate, and cached
    #     input (3_input_cached_actual) bills at ~10% of standard input
    #   - pricing is per model, so read actuals["models_used"]; a run can use more
    #     than one
    #   - decide where it lives: computing it in save_run_completion and storing it
    #     as an actual makes cost comparable across runs and keeps the report a
    #     pure projection. Computing it at report time keeps zeros out of every
    #     receipt while the tier is free. Receipt is probably right once pricing
    #     is real.
    # ... calculation logic ...

    return 0.0

@task
def save_run_completion(pipeline_id: str, run_id: str, llm_pass: str, status: str,
                        calls_file: Path) -> Path:
    """
    Write the run receipt (SOT for LLM pass completion within run). 
    A JSON record of one completed LLM pass — generation / enrichment 
    strategy (what ran and under what settings), token counts (cost 
    approximation), and status (success or failure).

    Full run-level traceability / reproducibility: 
    - run_manifest (what was planned, written before execution)
    - questions jsonl (the DTOs produced, one record per line)
    - calls jsonl (one accounting line per API call)
    - run_receipt *here* (summary of one LLM pass: settings, totals,
        status)      
    
    Each LLM pass within a run produces a receipt (e.g. generation, lexical
    enrichment, semantic enrichment). All passes of a run share a run_id, 
    so the full end-to-end picture is assembled by globbing that id (no single
    document reports the whole execution).

    Shared by generation and enrichment passes. The per-call records live 
    in `calls_file`, appended during the run; this method writes the run-level
    summary (identity, status, context, totals) and a pointer back to
    the records file. Deriving rather than accepting totals means the two levels
    (record files and receipt) cannot disagree.

    Args:
        pipeline_id: Versioned identifier for the pipeline code that ran.
        run_id: Run identifier.
        llm_pass: e.g. "generation", "lex_enrichment", "semantic_enrichment".
        status: "SUCCESS" or "FAILED".
        calls_file: Path to the file containing API call records.
        context: Settings the run executed under — model, prompt version,
            sampling parameters, and pass scope. This is what makes the run
            reproducible; it appears nowhere else.
    Returns:
        file_path for run receipt         
    """
    # read the call entries this run appended during execution
    with open(calls_file, "r", encoding="utf-8") as f:
        calls = [json.loads(line) for line in f if line.strip()]

    # Calculate run-total metrics from each llm call record
    token_totals ={}
    for c in calls:
        for key, value in c["tokens"].items():
            token_totals[key] = token_totals.get(key, 0) + value

    # Calculate the total number of records quarantined within the LLM pass
    # by failure cause - NOTE: currently will be empty for generation pass
    quarantine_totals = {}
    for c in calls:
        for failure_mode, count in (c['quarantined'] or {}).items():
            quarantine_totals[failure_mode] = quarantine_totals.get(failure_mode,0) + count       

    # create run reciept         
    completion_data = {
        "pipeline_id": pipeline_id,
        "run_id": run_id,
        "llm_pass": llm_pass,
        "status": status,
        "timestamp_end": datetime.now(timezone.utc).isoformat(),
        "calls_file": calls_file.name,
        "actuals": {
            "api_calls": len(calls),
            "strategies_run": sorted({c["question_type"] for c in calls}),
            "models_used": sorted({c["model"] for c in calls}),
            # chapters will only apply to generation pass, will be 0 for enrichment
            "chapters_processed": sum(c["chapter_count"] for c in calls if "chapter_count" in c),
            "questions_saved": sum(c["questions_saved"] for c in calls),
            "tokens": token_totals,
            "quarantined": quarantine_totals,
        },
    }

    # Save in the same logs folder with standardized name
    file_path = build_run_artifact_path(RUNS_DIR, run_id, llm_pass, RECEIPT)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(completion_data, f, indent=2)

    logger = get_run_logger()
    logger.info("🏁 Run receipt saved to: %s", file_path)
    return file_path

# create markdown rows for display table
def render_markdown_rows(rows:List[Tuple[str,Any]]) -> str:
    """
    Render label/value pairs as markdown table rows.

    Keeps the pipe syntax in one place so a formatting error cannot hide in
    one row of many. The caller supplies the header and separator.
    """
    return "\n".join(f"| **{label}** | {value}" for label, value in rows)

# generate a completion report
@task
def create_run_report(receipt_path: Path, output_root: Path):
    """
    Render a markdown summary of one completed LLM pass and publish it to the
    Prefect UI and the terminal.

    A projection of the run receipt: everything shown is read from the receipt
    file, never from in-memory run state. That means the report can only show
    what was actually recorded, and a report can be rendered for any past run
    from its receipt alone.

    Shared by generation and enrichment passes — the receipt's shape is the
    same for all three, so one report serves them all.

    Args:
        receipt_path: the receipt written by save_run_completion.
        output_root: where this pass wrote its question jsonl files, shown in
            the report so a reader can find them.
    """
    logger = get_run_logger()
    # create relative path for output artifacts in the report (for clarity)
    rel = output_root.relative_to(nb_cfg.PROJECT_ROOT)

    # 1. read from saved run report (SOT)
    with open(receipt_path, "r", encoding='utf-8') as f:
        receipt = json.load(f)
    
    actuals = receipt['actuals']
    tokens = actuals['tokens']
    run_id = receipt['run_id']
    pipeline_id = receipt['pipeline_id']
    llm_pass = receipt['llm_pass']    

    # 2. format list and dict fields for the table
    #    .get: receipts are durable and never migrated, so a reader must tolerate
    #    fields added after older receipts were written
    quarantined = actuals.get("quarantined") or {}
    quarantine_str = (
        ", ".join(f"{mode}: {n}" for mode, n in quarantined.items())
        if quarantined else "none"
    )

    # 3. Build the Markdown Report
    #    gather metrics for rendering
    global_metrics = [
        ('Run ID', f"{run_id}" ),
        ('Pipeline ID', f"{pipeline_id}"),
        ('Status',receipt['status'] ),
        ('Completed', receipt['timestamp_end'] ),
        ('Strategies run', ", ".join(actuals['strategies_run']) ),
        ('Models Active', ", ".join(actuals['models_used']) ),
    ]
    # drop chapters if it doesn't apply to this pass (enrichment has no chapters)
    if actuals["chapters_processed"]:
        global_metrics.append(("Chapters Processed", actuals["chapters_processed"]))

    metric_rows_llm_pass = [
        ('API calls', actuals['api_calls']),
        ('Input tokens', f"{tokens['1_input_template'] + tokens['2_input_payload']:,}"),
        ('Output tokens', f"{tokens['4_output_candidates']:,}"),
        ('Thinking tokens', f"{tokens['6_thinking_actual']:,}"),
        ('Total tokens',  f"**{tokens['5_total_billed']:,}**"),
        ('Questions saved', f"**{actuals['questions_saved']}**"),
        ('Quarantined', quarantine_str),
    ]
    report = f"""
# 🧙‍♂️ Harry Potter Trivia: {llm_pass.replace("_", " ").title()} Pass Report

| **Global Metric** | **Value** |
|:---|---:|
{render_markdown_rows(global_metrics)}

## 📊 Result Metrics

| Resource | Count |
|:---|---:|
{render_markdown_rows(metric_rows_llm_pass)}

## 📂 Output Artifacts
Questions: `{rel}/` (filenames start with `{run_id}_`)  
Call log: `{receipt['calls_file']}`  
Receipt: `{receipt_path.name}`
"""
    # 4.1. Create Prefect Artificat for dashboard
    create_markdown_artifact(
        key=f"report-{run_id}-{llm_pass}".replace("_", "-").lower(),
        markdown=report,
        description=f"Run summary: {run_id} / {llm_pass}"
        )

    # 4.2. Also publish report to console (Teriminal or not) using Rich
    console = Console()
    console.print("\n")
    console.print(Markdown(report))
    console.print("\n")

    # 5. Log to console
    logger = get_run_logger()
    logger.info("📝 Report created for %s: %s questions saved",
                llm_pass, actuals["questions_saved"])

## ORCHESTRATOR

@flow(name="Automated Question Generation")
def generate_questions_pipeline(target_books: List[Book],
                                target_chapters: Optional[List[int]] = None,
                                tasks_to_run: Optional[List[str]] = None,
                                chapter_limit: Optional[int] = None,
                                batch_size: int =2):
    """
   Orchestrates the full generation lifecycle: Initialization -> Manifest -> Batched 
   Execution -> Reporting.

    Args:
        target_books (List[Book]): The specific books to process.
        target_chapters (List[int], optional): Specific chapter numbers to target (e.g., `[1, 5]`).
        tasks_to_run (List[str], optional): Specific strategies to execute (e.g. 
            `["MCQ_Generation"]`). Defaults to ALL strategies if None.
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
        
    -----
    # TODO (caching): chapter-major loop + chapter-first prompts would make chapter
    # text cacheable across question types. Tracer: each chapter pair is sent once
    # per type, identical payload (11–18k tokens). Templates alone (768–1,684) are
    # all below the implicit-caching minimum, so template caching is not viable.
    # Ceiling: (k-1)/k of chapter sends cached at ~90% discount (k = question types;
    # 67% at k=3). Revisit when: moving off free tier, or full-corpus runs become
    # frequent. Requires a prompt experiment first — instruction/source ordering
    # affects output quality (see ex_primacy_bias).    
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
    calls_file = build_run_artifact_path(RUNS_DIR, run_id, LLM_PASS_GEN, CALLS)
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
                                      chapter_limit=chapter_limit)
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
                      LLM_PASS_GEN,
                      target_books,
                      chapter_file_paths,
                      run_timestamp,
                      run_scope)

    # A.8: Initialize
    #   initialize DTO list for all questions generated in this run
    all_draft_questions: List[DraftQuestion] = [] #type: ignore
    total_questions = 0  

    
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

        # CIRCUIT BREAKER: abort this strategy (q type) if too many jobs fail in a row
        # Scope: counter is per-strategy (resets between question types) and resets
        # on any successful job. 
        # > Initialize count for consecutive failures
        consecutive_failures = 0

        ## C. CHAPTER LOOP (JOB LEVEL)
        #     job / call = one API call over a chapter-chunk.
        #     Loop through batch_size number of chapters per loop (default = 2)
        for i, chapter_batch in enumerate(chunk_list(chapter_file_paths, batch_size)):
            # C.0: pacing (safe time delay for RPM limits) - sleep before each call except the first
            # TODO (pacing): only paces WITHIN a strategy — `i` resets per question type,
            # so the first job of each strategy fires straight after the previous
            # strategy's last call (with measure_template_tokens in that gap too).
            # Limits are per-key across all calls: loop position ≠ time since last call.
            # Proper fix: elapsed-time pacing at every call site. Low priority at 10 RPM.
            if i>0:
                delay = config.get('rate_limit_delay', 10)
                time.sleep(delay)

            # C.1: Safety check: abort run if consecutive failures reaches limit
            # Counts as a failure (cost spent, nothing saved) if: 
            #   (i) the API call raises, or (ii) 0 questions are parsed from the response.
            # Note: Malformed-but-present answers are validation pipeline scope not this breaker's
            if consecutive_failures >= MAX_FAILURES:
                logger.error("🚨 Aborting %s due to %s consecutive failures.",
                             task_name, MAX_FAILURES)
                break

            # C.2: Initialize 
            job_id = f"job_{short_uuid()}"
            # Extract names for metadata (since chapter_batch is a list of Paths)
            batch_names = [p.stem for p in chapter_batch]
            first_chap = chapter_batch[0].stem  # chapter ref in output filename and logging

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
                output_file = OUTPUT_DIR / f"{run_id}_{config['file_prefix']}_{first_chap}.jsonl"

                # C.6.2: parse and save as jsonl with Task
                call_entry, draft_questions = parse_and_save(
                    run_id, batch_id, job_id, response,
                    output_file=output_file,
                    calls_file=calls_file,
                    full_metadata=full_metadata,
                    chapter_count=len(chapter_batch),
                    template_token_count=template_token_count,
                )
                # collect draft questions from the job into run-level list
                all_draft_questions.extend(draft_questions)

                # C.7: Assess if run was a failure (no questions generated)
                # if successful update total question count else update failure counter
                if  len(draft_questions) > 0:
                    consecutive_failures = 0
                    total_questions += len(draft_questions) 
                else:
                    consecutive_failures += 1

            except Exception as e:  # pylint: disable=broad-exception-caught
                consecutive_failures += 1
                # TODO: a call that raised before returning has no usage data here,
                # so its tokens go unrecorded — the provider may still have billed
                # them. Closed when transport failures get their own call entry
                logger.error("Error on %s: %s", first_chap, e)
                continue

    ## D: WRAP-UP
    # D.1: run outcome for the receipt
    status = "SUCCESS" if total_questions > 0 else "FAILED"

    # D.2: summary report for Prefect UI / terminal
    # save actual metrics of run for traceability (run "reciept")
    receipt_path = save_run_completion(pipeline_id, run_id, LLM_PASS_GEN, status, calls_file)
    create_run_report(receipt_path, OUTPUT_DIR)
    # completion update
    logger.info("🏁 Genearation Completed: %s",run_id)
    
    return receipt_path, all_draft_questions  # return for testing and validation

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
        logger.error("\n💥 Pipeline crashed with critical error: %s", e)
        sys.exit(1)
