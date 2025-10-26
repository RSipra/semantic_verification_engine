import os
import yaml
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
# import google.generativeai as genai # No longer needed for the simulated test

# --- API Call Function (Placeholder for Testing) ---
# This is a simulated version of the API call function.
# It does not make a real network request and returns instant, fake data.
def call_gemini_api(prompt: str, model_name: str, parameters: dict) -> tuple[str, dict]:
    """
    Placeholder function that simulates a call to the Gemini API for testing.

    Returns:
        tuple[str, dict]: A tuple containing a simulated generated text (as a JSON string)
                          and simulated usage metrics.
    """
    print(f"      -> SIMULATING API call for model: {model_name}...")
    
    # Simulate a successful JSON response
    simulated_response_text = json.dumps({
        "questions": [
            {
                "question_type": "EX",
                "question": "This is a simulated question from the placeholder function.",
                "answer": "This is a simulated answer.",
                "difficulty": "Medium",
                "answer_variations": [
                    "This is a variation of the answer.",
                    "This is another similar answer."
                ]
            }
        ]
    })
    
    # Simulate the usage object from the API response with random-like numbers
    prompt_tokens = len(prompt.split())
    completion_tokens = len(simulated_response_text.split())
    simulated_usage = {
        'prompt_token_count': prompt_tokens,
        'candidates_token_count': completion_tokens,
        'total_token_count': prompt_tokens + completion_tokens
    }
    
    time.sleep(0.1) # Simulate a tiny bit of network latency
    return (simulated_response_text, simulated_usage)


# --- REAL API Call Function (Commented Out for Testing) ---
# def call_gemini_api(prompt: str, model_name: str, parameters: dict) -> tuple[str, dict]:
#     """
#     Makes an API call to the Google Gemini API and returns the response.
#     """
#     try:
#         api_key = os.getenv("GEMINI_API_KEY")
#         if not api_key:
#             raise ValueError("GEMINI_API_KEY environment variable not set.")
#         genai.configure(api_key=api_key)
#
#         print(f"      -> Calling Gemini API with model: {model_name}...")
#         
#         generation_config = genai.types.GenerationConfig(
#             candidate_count=1,
#             **parameters
#         )
#
#         model = genai.GenerativeModel(model_name)
#         
#         start_time = time.time()
#         response = model.generate_content(prompt, generation_config=generation_config)
#         end_time = time.time()
#         
#         print(f"      -> API call successful. Time taken: {end_time - start_time:.2f}s")
#
#         generated_text = response.text
#
#         usage_metrics = {
#             'prompt_token_count': response.usage_metadata.prompt_token_count,
#             'candidates_token_count': response.usage_metadata.candidates_token_count,
#             'total_token_count': response.usage_metadata.total_token_count
#         }
#
#         return (generated_text, usage_metrics)
#
#     except Exception as e:
#         print(f"      -> ERROR during API call: {e}")
#         return (json.dumps({"error": str(e)}), {'prompt_token_count': 0, 'candidates_token_count': 0, 'total_token_count': 0})


# --- Cost Estimation ---
# Update these prices based on the latest from your provider
MODEL_PRICING_USD_PER_MILLION_TOKENS = {
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50}
}

def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimates the cost of an API call in USD."""
    pricing = MODEL_PRICING_USD_PER_MILLION_TOKENS.get(model)
    if not pricing:
        return 0.0
    cost = (prompt_tokens / 1_000_000 * pricing['input']) + \
           (completion_tokens / 1_000_000 * pricing['output'])
    return round(cost, 6)

# --- Main Experiment Runner ---
def run_experiments(config_path: str = 'experiments.yaml', experiment_id_to_run: str = None, run_version_to_run: str = None):
    """
    Reads an experiment configuration file, runs defined experiments by processing
    pre-defined batches of source texts, and logs results back to the file.
    """
    # 1. Load the experiment configuration
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 2. Loop through each experiment and each run
    for experiment in config.get('experiments', []):
        exp_id = experiment.get('id', 'unknown_experiment')
        
        if experiment_id_to_run and exp_id != experiment_id_to_run:
            continue

        print(f"\n--- Starting Experiment: {exp_id} ---")

        output_dir = f"outputs/{exp_id}"
        os.makedirs(output_dir, exist_ok=True)
        
        safe_delay = experiment.get('api_limits', {}).get('safe_delay_seconds', 1)

        for run in experiment.get('runs', []):
            version = run.get('version', 'unknown_version')
            
            if run_version_to_run and version != run_version_to_run:
                continue

            if run.get('status') != 'pending':
                print(f"  - Skipping run '{version}': Status is '{run.get('status')}'.")
                continue

            print(f"  - Starting run '{version}'...")

            try:
                with open(run['prompt_file'], 'r', encoding='utf-8') as f:
                    prompt_template = f.read()
                
                source_file_batches = experiment.get('source_text_files', [])

                total_prompt_tokens, total_completion_tokens, total_cost, total_response_time = 0, 0, 0.0, 0.0
                output_paths = []
                start_timestamp = datetime.now().isoformat()

                for file_batch in source_file_batches:
                    if not isinstance(file_batch, list):
                        file_batch = [file_batch] 

                    combined_text = ""
                    basenames = []
                    for file_path in file_batch:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            combined_text += f.read() + "\n\n--- NEXT CHAPTER ---\n\n"
                        basenames.append(Path(file_path).stem)
                    
                    source_text = combined_text.strip()
                    source_basename = "_and_".join(basenames)

                    print(f"    - Processing batch: {source_basename}")
                    prompt_to_send = prompt_template.format(source_text=source_text)
                    
                    start_time_call = time.time()
                    generated_json, usage_metrics = call_gemini_api(
                        prompt=prompt_to_send,
                        model_name=experiment.get('model', 'default-model'),
                        parameters=run.get('parameters', {})
                    )
                    end_time_call = time.time()
                    
                    prompt_tokens = usage_metrics.get('prompt_token_count', 0)
                    completion_tokens = usage_metrics.get('candidates_token_count', 0)
                    total_prompt_tokens += prompt_tokens
                    total_completion_tokens += completion_tokens
                    total_cost += estimate_cost(experiment.get('model'), prompt_tokens, completion_tokens)
                    total_response_time += (end_time_call - start_time_call)

                    output_filename = f"{version}_{source_basename}_output.json"
                    output_path = os.path.join(output_dir, output_filename)
                    
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(json.loads(generated_json), f, indent=4)
                    output_paths.append(output_path)
                    
                    time.sleep(safe_delay)

                end_timestamp = datetime.now().isoformat()
                
                run['date'] = end_timestamp
                run['metrics'] = {
                    'tokens': {
                        'prompt': total_prompt_tokens,
                        'completion': total_completion_tokens,
                        'total': total_prompt_tokens + total_completion_tokens
                    },
                    'timing': {
                        'total_response_time_sec': round(total_response_time, 2),
                        'start_timestamp': start_timestamp,
                        'end_timestamp': end_timestamp
                    },
                    'cost_estimate_usd': total_cost
                }

                run['output_files'] = output_paths
                run['status'] = 'completed'
                print(f"    - Success! {len(output_paths)} output files saved to {output_dir}")

            except Exception as e:
                run['status'] = f'failed: {e}'
                print(f"    - ERROR on run '{version}': {e}")
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, sort_keys=False, indent=2, default_flow_style=False)

    print(f"\n--- All experiments finished. Results logged to '{config_path}' ---")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run prompt engineering experiments from a YAML config.")
    parser.add_argument('--config', type=str, default='experiments.yaml', help='Path to the YAML configuration file.')
    parser.add_argument('--id', type=str, help='(Optional) Run only the experiment with this ID.')
    parser.add_argument('--version', type=str, help='(Optional) Run only the run with this version string (requires --id).')
    
    args = parser.parse_args()
    
    run_experiments(config_path=args.config, experiment_id_to_run=args.id, run_version_to_run=args.version)

