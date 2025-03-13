"""
    Downloads the Harry Potter trivia dataset from Hugging Face, combines
    the train and test splits into a single DataFrame, and saves the result
    as a CSV file in the specified directory.
"""

import os
import pandas as pd
from datasets import load_dataset
from dotenv import load_dotenv

# Load the 'configure.env' file
load_dotenv('config.env')

# Define the dataset and save paths
DATASET_NAME = "saracandu/harry-potter-trivia-human"
SAVE_DIR = os.getenv('SAVE_DIR')
CSV_FILENAME = "harry_potter_trivia_questions_HFdataset.csv"

# Download the dataset from Hugging Face
print(f"Downloading the {DATASET_NAME} dataset...")
dataset = load_dataset(DATASET_NAME)

# Combine train and test splits into one DataFrame
train_df = pd.DataFrame(dataset["train"])
test_df = pd.DataFrame(dataset["test"])

# Concatenate the train and test DataFrames
combined_df = pd.concat([train_df, test_df], ignore_index=True)

# Save the combined DataFrame as a CSV file
csv_path = os.path.join(SAVE_DIR, CSV_FILENAME)
combined_df.to_csv(csv_path, index=False)
print(f"Combined dataset saved as CSV at: {csv_path}")
