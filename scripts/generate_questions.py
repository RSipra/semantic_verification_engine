"""
Trivia question generation pipeline 

Usage:
    # Run full pipeline
    $ python scripts/generate_questions.py

    # Run specific tasks only
    $ python scripts/generate_questions.py --tasks MCQ_Generation FR_Generation

Pipeline Flow: 

1. initiate at start:
    - generate pipeline_run_id, run_timestamp
    - configure logger to save to disk as well (task)
    - configure api (task)
    - Save Run Manifest (Task).
    - initialize run_stats dict (task)

2. Loop for strategy (EX, MCQ, FR)
    - generate batch_id
    - measure template tokens once (task)
    - retrieve chapters using `get_chapters` (task)
    - Initialize consecutive_failures = 0.
    
    3. loop for chapters
    - Check circuit breaker: if `consecutive_failures >= 5: break`
    - generate job_id 
    - prepare_prompt (task)
    
    try/except block
        4. make api call (task) - retries handled by task
        5. create strategy_batch_data (static data) with chapter names and job_id (dynamic)
        6. parse and save (task)
            6.1. layer 1 (helper): check if api call accepted or blocked and log feedback in metadata (safety)
            6.2. layer 2 (helper): calculate tokens breakdown for the job/response
            6.3. layer 3 (helper): process candidates, enrich with metadata, save to jsonl
        
        - On Success: consecutive_failures = 0. Update run_stats.
        - On Failure: consecutive_failures += 1. Log Error.
    
    7. Rate Limit Sleep: time.sleep(strategy.delay).

8. wrap-up pipeline run
    - summary report (artifact) - immediate summary markdown report for user in terminal
    - results file saved (json) / run log (task) - results report saved to file

"""
import os
from datetime import datetime, timezone
import time
import argparse
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import json
from dotenv import load_dotenv
import google.generativeai as genai
from prefect import flow, task, get_run_logger #pipeline orchestrator
from prefect.artifacts import create_markdown_artifact
from ds_utils.ds_constants import Book
import ds_utils.notebook_config as nb_cfg
from ds_utils.schemas import StandardQuestion, MCQuestion

## CONSTANTS

# Paths
PROMPTS_DIR = nb_cfg.PROMPTS_DIR
OUTPUT_DIR = nb_cfg.GENERATED_QUESTIONS_DIR
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

# Predefined models for each question type (model-per-type based on experimentation)
GENERATION_STRATEGY =[
    {
        "task_name": "EX_Generation",
        "model_name": "gemini-2.5-pro",
        "prompt_file": PROMPTS_DIR / "explanatory_master_prompt.txt",
        "file_prefix": "ex_questions",  # prefix to use in naming output files
        "json_response_schema": list[StandardQuestion],  # standardized schema
        "rate_limit_delay": 45,  # for 2 RPM limit (30s) plus additional margin
        "temperature": 0.7,
        "max_output_tokens": 12000,
        "top_p": 0.95,
        "candidate_count": 1 
    },
    {
        "task_name": "MCQ_Generation",
        "model_name": "gemini-2.5-pro",
        "prompt_file": PROMPTS_DIR / "mcq_master_prompt.txt",
        "file_prefix": "mcq_questions",
        "json_response_schema": list[MCQuestion],  # standardized schema
        "rate_limit_delay": 45,
        "temperature": 0.7,
        "max_output_tokens": 12000,
        "top_p": 0.95,
        "candidate_count": 1  
    },
    {
        "task_name": "FR_Generation",
        "model_name": "gemini-2.5-flash",
        "prompt_file": PROMPTS_DIR / "factual_recall_master_prompt.txt",
        "file_prefix": "fr_questions",
        "json_response_schema": list[StandardQuestion],
        "rate_limit_delay":  10,  # for 10 RPM limit (6s) plus additional margin
        "temperature": 0.7,
        "max_output_tokens": 12000,
        "top_p": 0.95,
        "candidate_count": 1 
    }
]

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
        
    logger.info(f"🎯 Strategy filtered to {len(active_strategy)} tasks: {tasks_to_run}")
    return active_strategy

@task  #configure the API
def configure_api(config_path:str) -> None:
    """Loads environment variables and configures the Gemini API."""
    load_dotenv(dotenv_path=config_path)
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY not found in the config file.")
    genai.configure(api_key=api_key)  # type: ignore
    
@task
def save_run_manifest(run_id: str, pipeline_id: str, strategy: list, target_books: list, chapters: list) -> None:
    """
    Saves the execution plan (*recipe*) before execution starts. This is to help distinguis 
    between attempted runs (e.g aborted, crashed) vs. successful runs (with full reporting, artifacts)
    
    Args:
        run_id: The unique UUID for this pipeline execution.
        pipeline_id: The versioned identifier for this script logic (e.g., 'pipe_q_gen_v0').
        strategy: The list of generation configs (models, prompts) to be executed.
        target_books: The specific list of Book enums targeted in this run.
    """
    # path to save run manifest to
    manifest_dir = MANIFESTS_DIR
    
    # Make strategy serializable (Path -> str)
    serializable_strategy = []
    for config in strategy:
        clean = config.copy()
        if isinstance(clean.get('prompt_file'), Path):
            clean['prompt_file'] = clean['prompt_file'].name
        # Remove schema class from log (not serializable)
        clean.pop('json_response_schema', None)
        serializable_strategy.append(clean)

    manifest = {
        "identifiers": {"run_id": run_id, "pipeline_id": pipeline_id},
        "timestamp_start": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "target_books": [b.name for b in target_books],
            "total_chapters": len(chapters), 
            "chapter_files": [p.name for p in chapters] 
        },
        "strategy": serializable_strategy
    }
    
    filename = f"{pipeline_id}_{run_id}_manifest.json"
    with open(manifest_dir / filename, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
        
    get_run_logger().info("Manifest saved: %s", filename)

@task # get list of Paths for all the chapters for select book ready for formatting the prompt template per run
def get_chapters(target_books: list[Book], target_book_folder: str = "06_books") -> List[Path]:
    """
    Scans the target folder and returns sorted Paths for all chapters 
    belonging to the specified Books. This task relies on the `Book` Enum class 
    (from `ds_utils.ds_constants`) to define the standardized filename prefixes
    (e.g., 'prisoner_of_azkaban_').
    Args:
        target_books (List[Book]): A list of Book Enum members defining which 
                                   books to process (e.g., [Book.BOOK_3, Book.BOOK_4]).
        target_book_folder (str): The subdirectory within 'data/' to search. 
                                  Defaults to "06_books".

    Returns:
        List[Path]: A list of pathlib.Path objects for every matching text file,
                    sorted alphanumerically to ensure deterministic processing order.
    """
    books_dir = nb_cfg.DATA_DIR / target_book_folder
    # convert Enums to a tuple of strings for startswith()
    prefixes = tuple(book.value for book in target_books)
    relevant_file_paths = [p for p in books_dir.iterdir() if p.name.startswith(prefixes)]
    return sorted(relevant_file_paths)

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

# To handle the 429 error caused by sliding window (exceeding RPM limit for free-tier) 
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
                                   chapter_names: List[str]) -> dict:
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
        "source_files": ", ".join(chapter_names),   # job level
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
def calculate_token_metrics(response, full_metadata: dict, template_token_count: int) -> Tuple[int, int, int]:
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
def process_and_save_candidates(job_id: str, response, output_file: Path,
                               full_metadata: Dict[str,Any], logger) -> int:
    """
    response processinglayer 3: core logic. Loops candidates, parses JSON
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
                logger.warning("❌ [job id: %s] JSON extraction failed for Candidate %s in %s", job_id, i, source_file)

        # Specific error handling
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as e:
            logger.error("[job id: %s] Data Error processing Candidate %s: %s", job_id, i, e)
            continue
        except OSError as e:
            logger.error("[job id: %s] File System Error saving Candidate %s: %s", job_id, i, e)
            continue
        except Exception as e:
            logger.error("[job id: %s] 💥 Critical Unexpected Error on Candidate %s: %s", job_id, i, e)
            continue
            
    return total_saved

# Process and save questions from candidates as individual entries in jsonl file
@task
def parse_and_save(job_id: str, response, output_file: Path, full_metadata: Dict[str,Any], 
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
    saved_count = process_and_save_candidates(job_id, response, output_file, full_metadata, logger)

    if saved_count > 0:
        logger.info("✅ [job id: %s] Saved %s questions. Total tokens: %s",
                    job_id, saved_count, total_billed)
    
    else: # explicitly log the zero question failure event + the cost incurred 
          # (call not blocked, but no questions to parse e.g. missing '[' delimiters], 
          # MAX_TOKENS hit in middle of first question, etc)
        logger.warning("⚠️ [job id: %s] 0 questions saved. Tokens wasted: %s", 
                       job_id, total_billed)    

    return saved_count, total_billed, t_in, t_out,

# placeholder for cost esmtimate helper if needed for later dataset expansion
def estimate_run_cost(total_input: int, total_output: int, models_used: list) -> float:
    """
    Placeholder for cost estimation. 
    Currently returns $0.00 for Free Tier runs.
    
    Future Logic (Pay-As-You-Go): UPDATE to most recent costs
    - Pro: ~$3.50 / 1M input, ~$10.50 / 1M output
    - Flash: ~$0.35 / 1M input, ~$1.05 / 1M output
    """
    # TODO: update if Paid Tier needed to expand dataset in later iterations
    # PRICING = {
    #     "PRO": {"input": 3.50, "output": 10.50},
    #     "FLASH": {"input": 0.35, "output": 1.05}
    # }
    # ... calculation logic ...

    return 0.0

# generate a completion report
@task
def create_run_report(run_id: str, run_stats: dict, output_root: Path):
    """
    Generates a Markdown summary of the run and publishes it to the Prefect UI.
    """
    # 1. Get (Placeholder) Cost
    # add step for cost estimation when needed
    
    # 2. Format Model List
    models_str = ", ".join(run_stats['models_used'])
    
    # 3. Build the Markdown Report
    # We emphasize Tokens and Counts over Cost for now
    report = f"""
# 🧙‍♂️ Harry Potter Generation Report

| **Global Metric** | **Value** |
|:---|---:|
| **Run ID** | `{run_id}` |
| **Date** | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} |
| **Runtime** | |
| **Chapters Processed** | {run_stats.get('chapters_processed', 0)} |
| **Models Active** | {models_str} |

## 📊 Volume Metrics

| Resource | Count |
|:---|---:|
| **Total Input Tokens** | {run_stats['total_input']:,} |
| **Total Output Tokens** | {run_stats['total_output']:,} |
| **Total Billed** | **{run_stats['total_billed']:,}** |
| **Questions Created** | **{run_stats['total_questions']}** |

## 📂 Output Artifacts
Files are saved in: `{output_root}/{run_id}/`
"""

    # 4. Publish to Prefect UI
    create_markdown_artifact(
        key=f"report-{run_id}",
        markdown=report,
        description=f"Run Summary: {run_id}"
    )
    
    # 5. Log to console
    logger = get_run_logger()
    logger.info("📝 Artifact created. Total Questions: %s", run_stats['total_questions'])
    
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

@task
def configure_file_logging(run_id: str):
    """
    Attaches a FileHandler to the Prefect logger so logs are saved to disk
    in addition to the Prefect UI/Database.
    """
    log_dir = LOGS_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / f"{run_id}.log"
    
    # Get the Prefect logger
    # Note: We hook into the root 'prefect' logger to capture everything
    logger = logging.getLogger("prefect")
    
    # Create file handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
    fh.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(fh)
    
    return str(log_file)

## ORCHESTRATOR

# @flow(name="Harry Potter Question Generation")
# def generate_questions_pipeline(
    # tasks_to_run: Optional[List[str]] = None,
    # chapter_limit: Optional[int] = None
    # ):
"""
    Orchestrates the end-to-end question generation workflow.
    
    This flow manages the lifecycle of a run:
    1.  **Initialization:** Sets up Run IDs, Logging, and API connections.
    2.  **Strategy Selection:** Filters the generation strategy based on `tasks_to_run`.
    3.  **Manifest:** Persists the 'Flight Plan' before execution begins.
    4.  **Execution:** Loops through strategies (EX, MCQ, FR) and chapters (Book 3, 4, 7).
    5.  **Reporting:** Generates artifacts and logs the final results.

    Args:
        tasks_to_run (List[str], optional): A list of specific task names to execute. 
            If None (default), ALL defined strategies in `GENERATION_STRATEGY` are run.
            Valid options: ["EX_Generation", "MCQ_Generation", "FR_Generation"]

    Examples:
        >>> # Run the full pipeline (All Question Types)
        >>> generate_questions_pipeline()

        >>> # Run ONLY Multiple Choice Questions
        >>> generate_questions_pipeline(tasks_to_run=["MCQ_Generation"])
        
        >>> # Run EX and FR, skipping MCQ
        >>> generate_questions_pipeline(tasks_to_run=["EX_Generation", "FR_Generation"])
    """
    
    # A. INITIALIZATION
    # run_id = f"run_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    # pipeline_id = PIPELINE_ID
    # run_timestamp = datetime.now(timezone.utc).isoformat()
    
    # # ... logging setup ...
    
    # # ... api setup ...
    
    # # B. STRATEGY SELECTION (The New Step)
    # # We do this EARLY so the Manifest reflects exactly what will run
    # active_strategy = filter_strategy(GENERATION_STRATEGY, tasks_to_run)
    
    # # Stop if filter resulted in empty list
    # if not active_strategy:
    #     get_run_logger().error("🛑 Pipeline aborted: No tasks to run.")
    #     return

    # # C. SAVE MANIFEST
    # # Now we pass 'active_strategy', so the file correctly records ONLY what we ran.
    # target_books = [Book.BOOK_3] 
    # chapters = get_chapters(target_books)
    
    # ... get chapters ...
    
    # # APPLY LIMIT (The Safety Valve)
    # if chapter_limit:
    #     logger.info(f"🛑 DEMO MODE: Limiting execution to first {chapter_limit} chapters.")
    #     chapters = chapters[:chapter_limit]
    
    # save_run_manifest(run_id, pipeline_id, active_strategy, target_books)
    
    # # ... (rest of flow uses 'active_strategy' instead of GENERATION_STRATEGY) ...

    # # D. THE LOOP
    # for config in active_strategy:
    #      # ... same loop logic as before ...



    # 1. Setup Run ID
    # run_id = f"run_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    
    # # 2. Configure Logging to File (NEW)
    # log_path = configure_file_logging(run_id)
    
    # logger = get_run_logger()
    # logger.info(f"🚀 Starting Pipeline: {run_id}")
    # logger.info(f"📄 Logs mirroring to: {log_path}")
    
    
    
    
    # 1. Generate Run ID (e.g., "run_20251119_a1b2c3d4")
    # # run_id = f"run_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:8]}"
    # print(f"🚀 Starting Pipeline Run: {run_id}")
    # run_stats = init_run_stats()

    # # 2. Create a specific folder for this run (Optional but cleaner)
    # # e.g., data/08_generated/run_20251119_a1b2c3d4/
    # run_output_dir = nb_cfg.DATA_DIR / "08_generated" / run_id
    # run_output_dir.mkdir(parents=True, exist_ok=True)

    # # 3. The Master Loop
    # for config in GENERATION_STRATEGY:
        
    #     # DYNAMIC FILENAME: Include the Run ID in the file name
    #     # e.g., "ex_questions_run_20251119_a1b2c3d4.jsonl"
    #     filename = f"{config['file_prefix']}_{run_id}.jsonl"
    #     output_path = run_output_dir / filename
        
    #     print(f"\n--- Starting Task: {config['task_name']} -> {filename} ---")
    # for chapter in chapters:
            # ... prepare prompt ...
            
            # response = call_model_api(prompt=final_prompt, config=strategy)
            
            # ... save data ...
            
            # PROACTIVE RATE LIMITING
            # Use the specific delay for this model
            # sleep_time = config.get('rate_limit_delay', 5) 
            # print(f"Sleeping for {sleep_time}s to respect rate limits...")
            # time.sleep(sleep_time)


# @flow
# def generate_questions_pipeline():
#     # LEVEL 1: PIPELINE (Global)
#     # Generated once per script execution
#     pipeline_run_id = f"pipe_{uuid.uuid4().hex[:8]}"
    
#     for config in GENERATION_STRATEGY:
#         # LEVEL 2: BATCH (Strategy)
#         # Generated once per Strategy Loop
#         batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        
#         for chapter in chapters:
#             # LEVEL 3: JOB (Trace)
#             # Generated once per Chapter Loop
#             job_id = f"job_{uuid.uuid4().hex[:8]}"
            
#             # ... call API ...
            
#             # Pass ALL three to your helper
#             meta = create_metadata(pipeline_run_id, batch_id, job_id, ...)

            # # Capture 4 values
                # q_count, t_total, t_in, t_out = parse_and_save(
                #     job_id, response, output_file, full_meta, template_tokens
                # )
                
                # if q_count > 0:
                #     consecutive_failures = 0
                #     run_stats["total_questions"] += q_count
                    
                #     # Accumulate EXACT values from API
                #     run_stats["total_billed"] += t_total 
                #     run_stats["total_input"] += t_in
                #     run_stats["total_output"] += t_out
                # else:
                #     # Even if we failed to save questions, we still paid for tokens!
                #     # Optional: You might want to track these as "wasted_tokens"
                #     run_stats["total_billed"] += t_total 
                #     consecutive_failures += 1

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
    
    parser.add_argument("--limit", type=int, help="Limit number of chapters (for testing).")
    
    # 3. Parse arguments
    args = parser.parse_args()
    
    # 4. Run the Flow
    # We pass the list directly to your flow
    generate_questions_pipeline(tasks_to_run=args.tasks, chapter_limit=args.limit)
    