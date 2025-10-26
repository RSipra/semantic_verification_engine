"""
Manual API Call Script for Prompt Engineering Proof of Concept.

This script is designed for a single, manual prompt using the
Google Gemini API. The purpose of this prompt is to understand api generated outputs,
develop the script with the core working API logistics, and experimnent
with prompt variations. This script will then be the base for building the 
automated generation script.

The script performs the following steps:
1.  **Setup**: Defines key parameters like the model name, temperature, and file paths.
2.  **API Configuration**: Loads the GEMINI_API_KEY from a .env file.
3.  **Prompt Preparation**: Reads a prompt template and source chapter texts from
    their respective files and combines them into a single, formatted prompt.
4.  **API Call**: Makes a single, real call to the Gemini API using the prepared prompt.
5.  **Response Handling**: Prints a detailed breakdown of the response to the console,
    including metadata and the formatted JSON output, and saves the raw JSON
    response to a file in the 'llm_outputs' directory.
"""

import os
import time
import json
from pathlib import Path
import google.generativeai as genai
from dotenv import load_dotenv

#1. --setup and test parameters--
TEMPERATURE_SETTING = 0.2  
MODEL_NAME = 'gemini-2.5-flash'
MAX_OUTPUT_TOKENS = 12000 # expected ~1500 tokens
TOP_P_SETTING = 0.95      # Standard default for top_p
EXPERIMENT_NAME = 'manual_api_calls_v0'

# Define paths
script_path = Path(__file__).resolve()
project_root = script_path.parents[3]  # (iterations -> prompts -> scripts -> root)
config_path = project_root / 'config.env'
prompt_path = project_root / 'scripts/prompts/iterations/ex_prompt_v0.txt'
chapters_folder = project_root / 'data/06_books'
output_dir = project_root / 'scripts/prompts/llm_outputs'
yaml_path = project_root / 'scripts/prompts/experiment.yaml'

# 2. --configure API--
load_dotenv(dotenv_path=config_path)
google_api_key = os.environ.get('GEMINI_API_KEY')
if not google_api_key:
    raise ValueError("Error: GOOGLE_API_KEY not found.")
genai.configure(api_key=google_api_key)  # type: ignore

# 3. --prepare the prompt--
prompt_template = prompt_path.read_text(encoding="utf-8")
# Read two chapters
chapter_1 = chapters_folder / 'prisoner_of_azkaban_chapter_19.txt'
chapter_2 = chapters_folder / 'goblet_of_fire_chapter_01.txt'
chapter_1_content = chapter_1.read_text(encoding="utf-8")
chapter_2_content = chapter_2.read_text(encoding="utf-8")
source_info = "Prisoner of Azkaban, Chapter 19 and Goblet of Fire, Chapter 1"
# combine the content
combined_chapter_content = f"{chapter_1_content}\n\n--- END OF CHAPTER ---\n\n{chapter_2_content}"

# Combine the template and the chapter text into the final prompt
final_prompt = prompt_template.format(
        chapter_text=combined_chapter_content,
        book_and_chapter=source_info
        )

# 4. --make the API call--
model = genai.GenerativeModel(MODEL_NAME)  # type: ignore

# Get an estimate of the template's token count BEFORE the call
prompt_template_token_estimate = model.count_tokens(prompt_template).total_tokens

print("--- Making a real API call ---")
start_time = time.time()
response = model.generate_content(
    final_prompt,
    generation_config=genai.GenerationConfig(  #  type: ignore
        temperature=TEMPERATURE_SETTING,         
        max_output_tokens=MAX_OUTPUT_TOKENS,  
        top_p=TOP_P_SETTING,               
        response_mime_type="application/json",
    )
)
end_time = time.time()
response_time = end_time - start_time

print("\n--- Extracted Attributes From the Response Object ---")
# Assessment of prompt before generation starts (entire API call)
print(f"Prompt Feedback: {response.prompt_feedback}")
# Assessment of the generated candidate in model output text
finish_reason = response.candidates[0].finish_reason
print(f"The finish reason is: {finish_reason}")   # debugging info
print(f"Response Time: {response_time:.2f} seconds")
print(f"Usage Metadata (from API): {response.usage_metadata}")

# 5. --handle the response--
print("\n--- Generated JSON Output ---")
json_output_text = response.text
# Parse the string into a Python object and pretty-print it
parsed_json = json.loads(json_output_text)
formatted_json_string = json.dumps(parsed_json, indent=2)
print(formatted_json_string)

# cost estimate basis
api_total_input_tokens = response.usage_metadata.prompt_token_count
api_output_tokens = response.usage_metadata.candidates_token_count
context_token_estimate = api_total_input_tokens - prompt_template_token_estimate

print("--- Token Counts for cost estimate ---")
print(f"- Input tokens (cached = prompt template): {prompt_template_token_estimate}")
print(f"- Input tokens (uncached = chapter text): {context_token_estimate}")
print(f"- Output tokens: {api_output_tokens}")
print(f"- Total Billed Tokens (from API): {response.usage_metadata.total_token_count}")

# save output to a file
output_filename = f"{EXPERIMENT_NAME}_output.json"
output_path = output_dir / output_filename
# Save the response text to the file
output_path.write_text(json_output_text, encoding="utf-8")

print(f"\n✅ Response successfully saved to: {output_path}")
