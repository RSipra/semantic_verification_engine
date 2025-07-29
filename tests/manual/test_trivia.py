# Testing Trivia class - core logic MVP - manual testing.

# Import module to test functions:
from dotenv import load_dotenv
load_dotenv() 
import pandas as pd
from HPtrivia_game.trivia_manager import Trivia 
import utils.utils_paths as up
import HPtrivia_game.constants as constants

# 1. Define JUST the filename
csv_name = constants.MVP_TRIVIA_CSV_NAME
total_questons = 10

# 2. Initialize Trivia with the filename
trivia_session =Trivia(csv_name)
print("--- Initial State ---")

# 3. Call the main .start() method to run the whole setup process
print("\n--- Starting Trivia Session Setup by calling .start() ---")
try:
    # .start() will call _load_dataset and _load_questions internally
    trivia_session.start(total_questons)
    print("...Setup complete!")

    # 4. Now, inspect the final state of the object
    print("\n--- Final State ---")
    print(trivia_session)

    # 5. Inspect the results directly from the object's attributes
    if trivia_session.trivia_df is not None:
        print("DataFrame Head:")
        print(trivia_session.trivia_df.head())
        
    loaded_questions = trivia_session.get_session_questions()
    if loaded_questions:    
        print(f"\nNumber of questions loaded: {len(loaded_questions)}")
        print("First selected question dictionary:")
        print(loaded_questions[0])
    
    else:
        print("DataFrame was not created.")

except Exception as e:
    print(f"\n--- AN ERROR OCCURRED ---")
    print(f"Error details: {e}")