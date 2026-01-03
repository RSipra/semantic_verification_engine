"""
This script reads Harry Potter book text from R data files (.rda) and saves each chapter
into separate .txt files for prompt engineering and question generation."""

import os
import pyreadr
def extract_chapters_to_txt(rda_file_path: str, 
                            book_name_for_file: str, 
                            output_folder: str = 'data/06_books'):
    """
    Reads an R data file (.rda) containing Harry Potter book text, and saves
    each chapter into a separate .txt file.

    Args:
        rda_file_path (str): The full path to the input .rda file.
        book_name_for_file (str): A clean, lowercase name for the book to use in filenames
                                  (e.g., 'philosophers_stone').
        output_folder (str): The directory where the chapter .txt files will be saved.
    """
    # 1. Read the .rda file
    try:
        # pyreadr returns a dictionary where the key is the object name in the R file
        result = pyreadr.read_r(rda_file_path)
    except Exception as e:
        print(f"ERROR: Could not read the .rda file at {rda_file_path}. Reason: {e}")
        return

    # 2. Extract the DataFrame ---
    # Use the book_name_for_file derived from the filename to find the data object
    if book_name_for_file not in result:
        print(f"ERROR: Couldn't find expected data object '{book_name_for_file}' in the .rda file.")
        print(f"  - Available objects in file: {list(result.keys())}")
        return

    book_df = result[book_name_for_file]

    # Get the name of the column containing the chapter text (it's the first and only one)
    text_column_name = book_df.columns[0]
    print(f"Found {len(book_df)} chapters.")

    # --- 4. Loop and Save Chapters ---
    # Iterate through each row of the DataFrame, where each row is a chapter
    for index, row in book_df.iterrows():
        chapter_number = index + 1
        chapter_text = row[text_column_name]

        # Create a standardized, unique filename for each chapter
        # e.g., 'philosophers_stone_chapter_01.txt'
        output_filename = f"{book_name_for_file}_chapter_{chapter_number:02d}.txt"
        output_path = os.path.join(output_folder, output_filename)

        # Write the chapter text to its own .txt file
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(chapter_text)
            print(f"  - Saved: {output_path}")
        except Exception as e:
            print(f"  - ERROR: Could not write file for chapter {chapter_number}. Reason: {e}")

    print(f"\nSuccessfully extracted all chapters to the '{output_folder}' directory.\n")


if __name__ == '__main__':
    # --- STANDALONE SCRIPT CONFIGURATION ---
    # The folder where your raw .rda files are located
    RAW_DATA_FOLDER = 'data/01_raw'

    # List of the book filenames you want to process
    BOOKS_TO_PROCESS = [
        #'philosophers_stone.rda',
        #'chamber_of_secrets.rda',
        'prisoner_of_azkaban.rda',
        'goblet_of_fire.rda',
        #'order_of_the_phoenix.rda',
        # 'half_blood_prince.rda', 
        'deathly_hallows.rda'
    ]

    # --- EXECUTION LOOP ---
    print("Starting HP Corpus Extraction...")
    for rda_filename in BOOKS_TO_PROCESS:
        # Construct the full path to the input file
        full_path = os.path.join(RAW_DATA_FOLDER, rda_filename)

        # Get book name from the filename (eg 'prisoner_of_azkaban.rda' -> 'prisoner_of_azkaban')
        book_name = rda_filename.replace('.rda', '')

        # Call the main function to process this book
        extract_chapters_to_txt(
            rda_file_path=full_path,
            book_name_for_file=book_name
        )

    print("All specified books have been processed.")
