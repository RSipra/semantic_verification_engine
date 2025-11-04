"""
Script to compile all LLM output JSON files and their run-level metadata
into two separate, clean CSV files for analysis.

This script creates:
1.  llm_runs_metadata.csv:
    - One row PER RUN.
    - Contains all run-level metadata: temperature, question_type,
      and all token counts (input, output, total, etc.).
    - This file is for cost and API management analysis.

2.  llm_questions_compiled.csv:
    - One row PER QUESTION.
    - Contains the question text, answer, candidate number, etc.
    - Includes 'full_run_id' as a key to link back to the metadata file.
    - This file is for quality and semantic analysis.
"""

import json
from pathlib import Path
import re
import pandas as pd
import yaml

def load_run_metadata(yaml_path: Path) -> pd.DataFrame:
    """
    Loads the experiments.yaml file and creates a DataFrame with all
    run-level metadata (temp, tokens, etc.).
    
    Returns:
        pd.DataFrame: One row per run, indexed by 'full_run_id'.
    """
    metadata_map = {}
    VALID_QUESTION_TYPES = ["MCQ", "EX", "FR", "YN", "UNKNOWN"]

    print(f"Loading run-level metadata from {yaml_path}...")
    try:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        for experiment in config.get('experiments', []):
            exp_id = experiment.get('id')
            common_temp = experiment.get('common_parameters', {}).get('temperature')

            question_type = experiment.get('question_type', 'unknown').upper() 
            if question_type not in VALID_QUESTION_TYPES:
                print(f"  Warning: Found unknown question_type '{question_type}' \
                    in experiment_id '{exp_id}'. Setting to 'UNKNOWN'.")
                question_type = "UNKNOWN"

            for run in experiment.get('runs', []):
                run_version = run.get('version')
                full_run_id = f"{exp_id}_{run_version}" 

                run_temp = run.get('model_parameters', {}).get('temperature')
                final_temp = run_temp if run_temp is not None else common_temp

                # Extract token data and other metrics
                metrics = run.get('metrics', {})
                tokens_data = metrics.get('tokens', {})
                
               # Extract individual token counts, defaulting to 0 if missing
                input_cached = tokens_data.get('input_cached', 0) or 0
                input_uncached = tokens_data.get('input_uncached', 0) or 0
                output = tokens_data.get('output', 0) or 0
                total = tokens_data.get('total', 0) or 0
                # Calculate the hidden processing tokens
                tokens_processing_hidden = 0
                if total > 0: # Only calculate if we have token data
                    tokens_processing_hidden = total - (input_cached + input_uncached + output)

                metadata_map[full_run_id] = {
                    'temperature': final_temp,
                    'run_version': run_version,
                    'experiment_id': exp_id,
                    'question_type': question_type,
                    'response_time_seconds': metrics.get('response_time_seconds'),
                    'finish_reason': metrics.get('finish_reason'),
                    'tokens_input_cached': input_cached,
                    'tokens_input_uncached': input_uncached,
                    'tokens_output_single_candidate': output,
                    'tokens_total': total,
                    'tokens_all_other_candidate_outputs_and_processing': tokens_processing_hidden 
                }

        print(f"Successfully loaded metadata for {len(metadata_map)} runs.")

        # Convert the map to a DataFrame, indexed by the run ID
        df_runs = pd.DataFrame.from_dict(metadata_map, orient='index')
        df_runs.index.name = 'full_run_id'
        return df_runs.sort_index()

    except Exception as e:
        print(f"Error reading or parsing YAML file at {yaml_path}: {e}")
        return pd.DataFrame()

def process_json_files(output_dir: Path) -> pd.DataFrame:
    """
    Scans the output_dir for .json files and parses them into a
    DataFrame containing all individual questions.
    
    Returns:
        pd.DataFrame: One row per question.
    """
    all_questions_data = []
    
    # Regex to parse filenames: (run_id)_candidate_(num).json
    filename_regex = re.compile(r'^(.*?)_candidate_(\d+)\.json$')

    json_files = list(output_dir.glob('*.json'))
    if not json_files:
        print(f"Error: No .json files found in {output_dir}")
        return pd.DataFrame()
        
    print(f"Found {len(json_files)} JSON files to process for questions...")

    for json_file_path in json_files:
        try:
            match = filename_regex.search(json_file_path.name)
            if not match:
                print(f"Skipping file with unexpected name: {json_file_path.name}")
                continue
            
            full_run_id = match.group(1)
            candidate_num = int(match.group(2))
            
            content = json_file_path.read_text(encoding='utf-8')
            question_list = json.loads(content)
            
            if not isinstance(question_list, list):
                print(f"Warning: Content of {json_file_path.name} is not a list. Skipping.")
                continue

            for i, question_data in enumerate(question_list):
                if not isinstance(question_data, dict):
                    print(f"Warning: Item {i} in {json_file_path.name} is not a dict. Skipping.")
                    continue
                
                all_questions_data.append({
                    'full_run_id': full_run_id, # This is the "key" to join on
                    'candidate_num': candidate_num,
                    'source_file': json_file_path.name,
                    'question_index_in_file': i,
                    'question_text': question_data.get('question', question_data.get('question_text')),
                    'answer_text': question_data.get('answer', question_data.get('answer_text')),
                    'difficulty': question_data.get('difficulty'),
                    'raw_question_data': json.dumps(question_data),
                    'source_chapters': question_data.get('source_reference', []),
                })

        except Exception as e:
            print(f"Error processing file {json_file_path.name}: {e}")

    if not all_questions_data:
        print("No data was successfully extracted from JSON files.")
        return pd.DataFrame()

    # --- Create DataFrame ---
    df_questions = pd.DataFrame(all_questions_data)
    return df_questions

def main():
    """Main execution function."""
    
    # --- 1. Define Paths ---
    project_root = Path.cwd()
    yaml_path = project_root / 'scripts' / 'prompts' / 'experiments.yaml'
    output_dir = project_root / 'scripts' / 'prompts' / 'llm_outputs'
    compiled_dir = output_dir / 'compiled'

    # --- 2. Create 'compiled' directory ---
    compiled_dir.mkdir(parents=True, exist_ok=True)

    if not yaml_path.exists():
        print(f"Error: 'experiments.yaml' not found at {yaml_path}")
        return
    if not output_dir.exists():
        print(f"Error: 'llm_outputs' directory not found at {output_dir}")
        return

    # --- 3. Load Metadata (File 1) ---
    df_runs = load_run_metadata(yaml_path)

    # --- 4. Process Questions (File 2) ---
    df_questions = process_json_files(output_dir)

    # --- 5. Save Both Files ---
    if not df_runs.empty:
        output_path = compiled_dir / 'ex_temp_runs_metadata.csv'
        df_runs.to_csv(output_path, index=True, encoding='utf-8') # index=True to save the 'full_run_id'
        print(f"\nSuccessfully saved Run Metadata to '{output_path}'")
        print(df_runs.info())
    else:
        print("\nRun metadata DataFrame is empty. No file saved.")
        
    if not df_questions.empty:
        output_path = compiled_dir / 'ex_temp_questions_compiled.csv'
        df_questions.to_csv(output_path, index=False, encoding='utf-8')
        print(f"\nSuccessfully saved Questions to '{output_path}'")
        print(df_questions.info())
    else:
        print("\nQuestions DataFrame is empty. No file saved.")

if __name__ == "__main__":
    main()
