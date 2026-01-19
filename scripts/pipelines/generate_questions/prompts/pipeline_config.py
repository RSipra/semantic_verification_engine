'''
Configuration for offline pipelines
'''

import ds_utils.notebook_config as nb_cfg
from ds_utils.schemas import StandardQuestion, MCQuestion

# Predefined models for each question type (model-per-type based on experimentation)
GENERATION_STRATEGY =[
    {
        "task_name": "EX_Generation",
        "model_name": "gemini-2.5-pro",
        "prompt_id": "EX_v0",
        "prompt_file": nb_cfg.PROMPTS_DIR / "explanatory_master_prompt_v0.txt",
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
        "prompt_id": "MCQ_v0",
        "prompt_file": nb_cfg.PROMPTS_DIR / "mcq_master_prompt_v0.txt",
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
        "prompt_id": "FR_v0",
        "prompt_file": nb_cfg.PROMPTS_DIR / "factual_recall_master_prompt_v0.txt",
        "file_prefix": "fr_questions",
        "json_response_schema": list[StandardQuestion],
        "rate_limit_delay":  10,  # for 10 RPM limit (6s) plus additional margin
        "temperature": 0.7,
        "max_output_tokens": 12000,
        "top_p": 0.95,
        "candidate_count": 1 
    }
]