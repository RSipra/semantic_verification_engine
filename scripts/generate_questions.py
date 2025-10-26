import os
# import mode e.g. openai
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

PROMPT_FILE = "prompts/explanatory_prompt.txt"
CHAPTER_TEXT_FILE = "chapters/book4_chapter1.txt"
NUMBER_OF_QUESTIONS = 5
MODEL = "gpt-4o"

# --- 1. LOAD THE PROMPT TEMPLATE FROM THE FILE ---
with open(PROMPT_FILE, "r") as f:
    prompt_template = f.read()

# --- 2. LOAD THE SOURCE TEXT ---
with open(CHAPTER_TEXT_FILE, "r") as f:
    chapter_text = f.read()

# --- 3. "HYDRATE" THE PROMPT WITH YOUR VARIABLES ---
# This replaces the placeholders in your prompt file with the actual content
final_prompt = prompt_template.replace("{NUMBER}", str(NUMBER_OF_QUESTIONS))
final_prompt = final_prompt.replace("{Your Harry Potter chapter text goes here}", chapter_text)

# --- 4. MAKE THE API CALL ---
# response = openai.chat.completions.create(
#     model="gpt-4o",
#     messages=[
#         {"role": "user", "content": final_prompt}
#     ]
# )

# print(response.choices[0].message.content)

# Securely get your API key
# Make sure you have a .env file with: OPENAI_API_KEY="sk-..."
# client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def generate_questions(source_text: str, num_questions: int = 5) -> str:
    """
    Generates trivia questions using an LLM based on a provided source text.

    Args:
        source_text (str): The text from the Harry Potter books to base questions on.
        num_questions (int): The number of questions to generate.

    Returns:
        str: The raw JSON string response from the API, or an error message.
    """
    try:
        # Format the master prompt with the specific inputs
        formatted_prompt = MASTER_PROMPT.format(
            source_text=source_text,
            num_questions=num_questions
        )

        # Make the API call
        response = client.chat.completions.create(
            model=MODEL
            messages=[{"role": "user", "content": final_prompt}],
            temperature=0.7, # Adjust for creativity
            response_format={"type": "json_object"} # If using a model that supports JSON mode
        )
        
        # Extract the content from the response
        generated_content = response.choices[0].message.content
        return generated_content

    except Exception as e:
        print(f"An error occurred: {e}")
        return f"Error: {e}"

if __name__ == '__main__':
    # This block allows you to test the script directly from the command line
    sample_source = "Albus Dumbledore was the Headmaster of Hogwarts. He had a long, silver beard."
    
    print("--- Generating sample questions ---")
    questions_json = generate_questions(sample_source, num_questions=2)
    print(questions_json)
