'''
Configuration for offline pipelines
'''

import notebook_support.notebook_config as nb_cfg
from notebook_support.schemas import StandardQuestion, MCQuestion

# Predefined models for each question type (model-per-type based on experimentation)

# version of the generation strategy (for reproducibility and tracking)
GEN_STRATEGY_VERSION = "generation_strategy_v1.0"  

GENERATION_STRATEGY =[
    {
        "task_name": "EX_Generation",
        "model_name": "gemini-3.1-flash-lite",
        "prompt_id": "EX_v0",
        "prompt_file": nb_cfg.PROMPTS_DIR / "ex_master_prompt_v0.2.txt",
        "file_prefix": "ex_questions",  # prefix to use in naming output files
        "json_response_schema": list[StandardQuestion],  # standardized schema
        "rate_limit_delay": 10,   # for 10 RPM limit (6s) plus additional margin
        "temperature": 0.7,
        "max_output_tokens": 12000,
        "top_p": 0.95,
        "candidate_count": 1 
    },
    {
        "task_name": "MCQ_Generation",
        "model_name": "gemini-3.1-flash-lite",
        "prompt_id": "MCQ_v0",
        "prompt_file": nb_cfg.PROMPTS_DIR / "mcq_master_prompt_v1.1.txt",
        "file_prefix": "mcq_questions",
        "json_response_schema": list[MCQuestion],  # standardized schema
        "rate_limit_delay": 10,
        "temperature": 0.7,
        "max_output_tokens": 12000,
        "top_p": 0.95,
        "candidate_count": 1  
    },
    {
        "task_name": "FR_Generation",
        "model_name": "gemini-3.1-flash-lite",
        "prompt_id": "FR_v0",
        "prompt_file": nb_cfg.PROMPTS_DIR / "fr_master_prompt_v0.3.txt",
        "file_prefix": "fr_questions",
        "json_response_schema": list[StandardQuestion],
        "rate_limit_delay":  10,  # for 10 RPM limit (6s) plus additional margin
        "temperature": 0.7,
        "max_output_tokens": 12000,
        "top_p": 0.95,
        "candidate_count": 1 
    }
]