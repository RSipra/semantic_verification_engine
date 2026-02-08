"""
Auotmated Experiment Runner for Prompt Engineering with Gemini API

This script contains a set of helper functions and a main orchestrator to run
prompt engineering experiments defined in a YAML file. It reads "pending" tasks,
calls the Gemini API, then logs all quantitative metrics and output file paths
back to the YAML file, creating a reproducible experiment log.
"""
import os
from datetime import datetime, timezone
import time
from pathlib import Path
import yaml
from dotenv import load_dotenv
import google.generativeai as genai

## -- Helper Methods --

#1. setup up file paths
def setup_file_paths()-> dict:
    """Defines and returns the project root and key config file paths"""
    script_path = Path(__file__).resolve()
    # Go up 4 levels: iterations (source) -> question_generation -> research -> scripts -> Harry_Potter_Trivia (project root)
    project_root = script_path.parents[4]
    output_dir = project_root / 'scripts/research/question_generation/tracer_dataset_generation/llm_outputs'
    # future-proofing to ensure the directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
    'project_root' : project_root, 
    'config' : project_root / 'config.env',
    'yaml' : project_root / 'scripts/research/question_generation/tracer_dataset_generation/phase2_tracer_v0_synthetic_generation.yaml',
    'output_dir': output_dir
    }

#2. load yaml file
def load_experiment_config(yaml_path: Path):
    """Loads the experiment configuration from the YAML file"""
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

#3. configure the API
def configure_api(config_path:str) -> None:
    """Loads environment variables and configures the Gemini API."""
    load_dotenv(dotenv_path=config_path)
    api_key = os.environ.get('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("Error: GEMINI_API_KEY not found in the config file.")
    genai.configure(api_key=api_key)  # type: ignore

#4. prepare the prompt
def prepare_prompt(run_config: dict, paths: dict) -> tuple[str, str]:
    """
    Assembles the complete, formatted prompt string for a single experiment run.
    This function reads the configuration for a specific run, loads the appropriate
    prompt template and all specified source text files, combines the source texts,
    and injects the combined content into the template's placeholders.
    Args:
        run_config (dict): The configuration dictionary for the specific run,
            loaded from the YAML file. Expected to contain 'prompt_file' and
            'source_text_files' keys.
        paths (dict): A dictionary containing key file paths, including the
            'project_root'.
    Returns:
        final_prompt: The fully formatted prompt string.
    """
    # Get the project root from the 'paths' dictionary
    project_root = paths['project_root']
    # get the prompt template location for the specific experiment run and read it
    prompt_template_path = project_root / run_config['prompt_file']
    prompt_template = prompt_template_path.read_text(encoding="utf-8")
    
    # Integrity checks for the prompt template from unit testing
    #1. incase the prompt template is empty
    if not prompt_template or prompt_template.isspace():
        raise ValueError(f"Prompt template file is empty: {run_config['prompt_file']}")
    #2. if the prompt template doesn't have a placeholder for the chapters (source text)    
    if "{source_text}" not in prompt_template:
        raise ValueError("Prompt template is missing the required '{source_text}' placeholder.")
    #3. if the prompt template doesn't have a placeholder for the source info (references)    
    if "{valid_source_list}" not in prompt_template:
        raise ValueError(f"Prompt template {run_config['prompt_file']} is missing the required '{{valid_source_list}}' placeholder.")
    
    # Read and combine the source text files from the run configuration
    source_texts = []
    # in cases there are nested list of chapter pairs to combine
    for file_batch in run_config.get('source_text_files', []):
        # get each chapter within given batch
        for file_path in file_batch:
            full_path = project_root / file_path
            # Prevent silent failure (empty source files)
            text_content = full_path.read_text(encoding="utf-8")
            if not text_content or text_content.isspace():
                raise ValueError(f"Source file is empty or contains only whitespace: {file_path}")
            # ----------------------------------------
            source_texts.append(full_path.read_text(encoding="utf-8"))
    combined_text = "\n\n--- END OF CHAPTER ---\n\n".join(source_texts)
    # get the book and chapter reference
    source_options_list = run_config.get('source_info', [])
    if not source_options_list:
        raise ValueError(f"Run {run_config.get('version')} is missing the 'source_info' list in the YAML.")
    # Format that Python list into a clean, bulleted string
    formatted_options_str = "\n".join(f"- \"{option}\"" for option in source_options_list)
    
    # asselmble and return the final prompt
    final_prompt = prompt_template.format(
        source_text=combined_text,
        valid_source_list=formatted_options_str
        )
    return final_prompt, prompt_template

#5. Get an estimate of the template's token count BEFORE the call
def get_prompt_template_token_count(model: genai.GenerativeModel, prompt_template: str) -> int:  #type: ignore
    """Estimates the token count of the prompt template using the model's counting feature.
    Args:
        model (genai.GenerativeModel): The Gemini model instance to use for token counting.
        prompt_template (str): The prompt template string (without source text filled in).
    Returns:
        int: The estimated token count of the prompt template.
    """

    prompt_template_token_estimate = model.count_tokens(prompt_template).total_tokens
    return prompt_template_token_estimate

# 6. make the API call based on parameters assembeld by the Orchestrater
# Arguments are assembled by the Orchestrater from common and specific run parameters
def make_api_call(model: genai.GenerativeModel, final_prompt:str, final_parameters: dict) -> tuple:  #type: ignore
    """"Makes the API call to the Gemini model with the given parameters.
    Args:
        model (genai.GenerativeModel): The initialized Gemini model object.
        final_prompt (str): The complete, formatted prompt string to send.
        final_parameters (dict): A dictionary of generation parameters (temp, top_p, etc.)
    Returns:
        tuple: A tuple containing:
            - The raw 'GenerateContentResponse' object from the API.
            - The response time in seconds (float).
    """
    # Configure generation settings
    generation_config = genai.GenerationConfig(  # type: ignore
        **final_parameters,
        response_mime_type="application/json"
        )
    # make the API call and return values
    print("--- Making the API call ---")
    start_time = time.time()

    response = model.generate_content(final_prompt, generation_config=generation_config)
    end_time = time.time()
    response_time = end_time - start_time

    return response, response_time

#7. extract response metadata
def extract_metrics(response, response_time: float, prompt_template_tokens: int) -> dict:
    """
    Parses the raw API response object and calculates the final metrics log.
    """
    # Gracefully get the finish reason
    finish_reason = None
    if getattr(response, 'candidates', None):
        finish_reason = response.candidates[0].finish_reason.name

    # Get usage metadata
    usage_metadata = getattr(response, 'usage_metadata', {})
    
    if usage_metadata:
        # The real object uses dot-notation, not .get()
        # We use getattr() to safely access attributes, which is the
        # equivalent of .get() for objects.
        api_total_input = getattr(usage_metadata, 'prompt_token_count', 0)
        api_output = getattr(usage_metadata, 'candidates_token_count', 0)
        total_tokens = getattr(usage_metadata, 'total_token_count', 0)
    else:
        # Handle case where usage_metadata is missing entirely
        api_total_input = 0
        api_output = 0
        total_tokens = 0

    # Perform your token calculations
    cached_tokens = prompt_template_tokens
    uncached_tokens = api_total_input - cached_tokens

    metrics = {
        'response_time_seconds': round(response_time, 2),
        'finish_reason': finish_reason,
        'prompt_feedback': str(getattr(response, 'prompt_feedback', 'N/A')),
        'tokens': {
            'input_cached': cached_tokens,
            'input_uncached': uncached_tokens,
            'output': api_output,
            'total': total_tokens
        }
    }
    return metrics 

#8. save the response
def save_response_to_files(response: "genai.types.GenerateContentResponse",  #type: ignore
                           run_config: dict,
                           experiment_config: dict,
                           paths: dict) -> list[str]:
    """
    Saves the text from each candidate in the API response to its own unique JSON file.

    Args:
        response: The raw response object from the Gemini API.
        run_config: The config for the specific run (for naming).
        experiment_config: The config for the parent experiment (for naming).
        output_dir (Path): The Path object for the directory to save files in.

    Returns:
        A list of string paths to the newly created files.
    """
    output_files_list = []
    output_dir = paths['output_dir']

    if response.candidates:
        for i, candidate in enumerate(response.candidates):
            # Create a unique, descriptive filename for each candidate
            base_filename =f"{experiment_config['id']}_{run_config['version']}_candidate_{i+1}.json"
            output_path = output_dir / base_filename

            try:
                # Extract the text content
                candidate_text = candidate.content.parts[0].text
                # Save the raw JSON text to the file
                output_path.write_text(candidate_text, encoding="utf-8")
                output_files_list.append(str(output_path))
                print(f"  -> ✅ Candidate {i+1} saved to: {output_path.name}")
            except Exception as e:
                print(f"  -> ERROR saving candidate {i+1}: {e}")
    else:
        print("  -> No candidates found in response. Nothing to save.")

    return output_files_list

#9. update yaml with experiment run metrics and update status and status history
def log_run_results(run_config: dict,
                    metrics_dict: dict,
                    output_file_paths: list[str]):
    """
    Modifies the run_config dictionary in-place, filling it with the
    quantitative metrics and output file paths from the API call.
    """
    # 1. Update the status to 'completed'
    run_config['status'] = 'completed'

    # 2. Add the list of new file paths
    run_config['output_files'] = output_file_paths

    # 3. Add a new entry to the 'status_history'
    if 'status_history' not in run_config or not isinstance(run_config['status_history'], list):
        run_config['status_history'] = []

    run_config['status_history'].append({
        'status': 'completed',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

    # 4. Add the metrics
    if 'metrics' not in run_config or not isinstance(run_config['metrics'], dict):
        run_config['metrics'] = {}
    if 'tokens' not in run_config['metrics'] or not isinstance(run_config['metrics']['tokens'], dict):
        run_config['metrics']['tokens'] = {}
    run_config['metrics'] = metrics_dict

#10. log run in case of failure
def log_run_failure(run_config: dict, error: Exception):
    """
    Modifies the run_config dictionary in-place to log a 'failed' status.
    """
    # 1. Update the status to 'failed'
    run_config['status'] = 'failed'
    
    # 2. Add the error message to the 'notes' for debugging
    run_config['notes'] = f"Run failed with error: {str(error)}"

    # 3. Add a new entry to the 'status_history'
    if 'status_history' not in run_config or not isinstance(run_config['status_history'], list):
        run_config['status_history'] = []
        
    run_config['status_history'].append({
        'status': 'failed',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

## -- Orchestrater --

def main():
    """Orchestrates the end-to-end experiment runs based on the YAML configuration 
    where status is 'pending'."""

    # 1. setup file paths -
    paths = setup_file_paths()
    # create shorthand variables
    config_path = paths['config']
    yaml_path = paths['yaml']

    #2. load config and experiment parameters from YAML - experiments with status "pending"
    experiment_config = load_experiment_config(yaml_path)

    #3. configure the API
    configure_api(config_path)
    # safe delay to keep RPM within free-tier limits
    # Pro Free Tier (2 RPM)  -> 35 seconds
    # Flash Free Tier (10 RPM) -> 7 seconds
    DELAY_BETWEEN_CALLS_SECONDS = 65
    
    #4. Process all the experiments wit "pending" runs
    for experiment in experiment_config.get('experiments', []):
        # 4.1. Get the common parameters for this experiment.
        common_params = experiment.get('common_parameters', {})
        # 4.2. load the pending experiment runs
        for run in experiment.get('runs', []):
            
            model = genai.GenerativeModel(experiment['model']) # type: ignore
            if run.get('status') != 'pending':
                continue
            print(f"\n--- Executing run: {run['version']} ---")
            try:   
                # 4.3. Get the specific model parameters for this run.
                run_params = run.get('model_parameters', {})

                # 4.4. consolidate common and specific parameters
                final_parameters_for_call = common_params.copy()
                # Update/override them with the specific run parameters.
                final_parameters_for_call.update(run_params) 

                # 4.5. prepare the prompt
                final_prompt, prompt_template = prepare_prompt(run, paths)
                # 4.6. make the API call
                response, response_time = make_api_call(model, final_prompt, final_parameters_for_call)
                # 4.7. estimate the prompt template token count
                prompt_template_token_estimate = get_prompt_template_token_count(model, prompt_template)
                # 4.8. extract response metadata
                metrics_dict = extract_metrics(response, response_time, prompt_template_token_estimate)

                # 4.9. save all the candidate responses to file
                output_file_paths = save_response_to_files(response,run,experiment,paths)

                # 4.10. log the run results back to the run config
                log_run_results(run, metrics_dict, output_file_paths)
                print(f"  -> Run '{run['version']}' completed successfully.")
                
                # 4.11 add safe time delay to stay in free-tier RPM 
                time.sleep(DELAY_BETWEEN_CALLS_SECONDS)
                print(f"waiting {DELAY_BETWEEN_CALLS_SECONDS}s before next call")
            
            except Exception as e:
                print(f"  -> ERROR on run '{run['version']}': {e}")
                log_run_failure(run, e)
                
    # 5. Save the updated config data back to the YAML file
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(experiment_config, f, sort_keys=False, indent=2, width=1000)
    
    print("\n--- All pending experiments finished. Results logged. ---")

if __name__ == '__main__':
    main()
