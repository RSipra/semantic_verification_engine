"""
Docstring for ds_utils.tracer_utils

"""

from pathlib import Path
import re
import json
import pandas as pd

# helper method to sort files before chunking so that same question types appear together
def get_tracer_sort_key(path: Path) -> tuple:
    """
    Generates a sort key to group files by Type (MCQ, FR, EX) 
    and then by numerical sequence (Chapter or Batch ID).
    """
    name = path.name.upper()

    # 1. Type Priority: Keeps same-format questions in the same API call
    if "_EX_" in name: 
        q_prio = 1
    elif "_FR_" in name: 
        q_prio = 2
    elif "_MCQ_" in name: 
        q_prio = 3
    else: 
        q_prio = 4  # Default for Legacy 'batch_x' files

    # 2. Numerical Sequence: Finds the last number (avoids 'phase2' or 'v0' traps)
    import re
    all_nums = re.findall(r'\d+', name)
    num_val = int(all_nums[-1]) if all_nums else 0

    return (q_prio, num_val)

# create yaml runs for each Tracer dataset batch        
def generate_experiment_yaml(
    batch_dir: Path, 
    master_prompt: Path, 
    experiment_id: str, 
    description: str,
    project_name: str = "Semantic Verification Engine (Ref. Implementation: Harry Potter Trivia)",
    batch_size: int = 1,
    limit: int = 0
):
    """
    Scans the batch folder and creates a structured dictionary 
    compatible with the experiment script's YAML format.
    """
  
    # 1. Get all .json files in the batch folder and sort them numerically
    batch_files = sorted(list(batch_dir.glob("*.json")), key=get_tracer_sort_key)
        
    runs = []
    # 2. create yaml run content 
    runs = []
    for f in batch_files:
        if "_staging_" in f.stem:
            # For Synthetic: "phase2_v0_synthetic_staging_EX_batch_01" -> "EX_batch_01"
            version_name = f.stem.split('_staging_')[-1]
        else:
            # For Legacy: "batch_1" -> "batch_1"
            version_name = f.stem
        
        # convert paths to relative paths str for YAML
        rel_prompt = "scripts/" + str(master_prompt).rsplit('scripts/', maxsplit=1)[-1]
        rel_data_path = "scripts/" + str(f).rsplit('scripts/', maxsplit=1)[-1] 
        
        runs.append({
            'version': version_name,
            'prompt_file': rel_prompt,
            'data_file': rel_data_path,
            'output_files': None,
            'metrics':{
                'response_time_seconds': None,
                'finish_reason': None,
                'prompt_feedback': None,
                'tokens': {
                    'input_cached': None,
                    'input_uncached': None,
                    'output': None,
                    'total': None
                }
            },
            'status': 'pending',
            'notes': f"Automated run for {f.name}",
            'status_history': []
        })

    # 3. LIMIT: Applied to the completed RUNS    
    if limit > 0:
        runs = runs[:limit]
        print(f"🛠️  TRACER MODE: Generated {len(runs)} run(s) (Batch Size: {batch_size}).")
            
    # 4. Build the full experiment object
    experiment_data = {
        'metadata':{
            'project': project_name,
            'owner': 'reema sipra',
            'description': description,
            'question_types': ['MCQ', 'FR', 'EX'],
            'version': 0
            },
        'experiments': [
            {
            'id': experiment_id,
            'model': 'models/gemini-2.5-flash',
            'question_types': ['MCQ', 'FR', 'EX'],
            'common_parameters': {
                'max_output_tokens': 30000,
                'top_p': 0.95,
                'candidate_count': 1
                },
            'runs': runs
           }
        ]
    }

    return experiment_data

def merge_llm_batch_responses(llm_output_dir: Path, batch_prefix: str) -> pd.DataFrame:
    """"
    Filters, loads, and consolidates multiple JSON batch files into a single Pandas DataFrame.
    
    This function handles the transition from discrete JSON list batches to a unified 
    tabular format, aligning differing schemas (e.g., MCQ vs. FR) by padding missing 
    fields with NaNs.

    Args:
        llm_output_dir (Path): The directory containing the LLM response JSON files.
        batch_prefix (str): The filename prefix used to filter for specific experiment runs.

    Returns:
        pd.DataFrame: A consolidated DataFrame containing all experiment records with 
                     standardized 'original_question_id' column.
    """
    # 1. Filter: create a list of all batch files names that match the batch prefix
    search_pattern = f"{batch_prefix}*.json"
    files = list(llm_output_dir.glob(search_pattern))

    # 2. Consolidate: loop through each file and merge contents into a list
    master_list = []
    for json_file in files:
        with open(json_file, 'r', encoding='utf-8') as f:
            batch_data = json.load(f)
            master_list.extend(batch_data)

    # 3. convert master list to df
    consolidated_df = pd.DataFrame(master_list)

    # 4. print confirmation and return
    print(f"✅ Merged {len(files)} files with total {consolidated_df.shape[0]} entries.")
    return consolidated_df
