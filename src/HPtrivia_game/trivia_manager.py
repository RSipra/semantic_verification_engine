'''
====================================================================================
HARRY POTTER TRIVA GAME 
====================================================================================

CLI MVP (core logic) -> trivia module (data)

------------------------------------------------------------------------------------

This module manages the core trivia game functionality, including:
- Loading and storing trivia questions
- Handling question presentation and answer validation
- Scoring logic and question progression

Classes:
    - Trivia (load session trivia questions)
    - Question (responsible for individual question and answer logic)

Functions:
    - _load_dataset(): Loads selected csv file and creates the trivia dataframe
    - _load_questions(): Loads questions from trivia dataframe to a dictionary 
    - validate_answer(): Checks if a player's answer is correct

This module is typically used by the GameController during gameplay.

------------------------------------------------------------------------------------- 
  '''
# Import necessary libraries:
from dataclasses import dataclass, field
from importlib import resources 
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections.abc import Sequence
import ast
import pandas as pd
from pandas.errors import EmptyDataError, ParserError
import HPtrivia_game.constants as const
from utils import utils_general as ut

# --- NO NEED TO MANUALLY WRITE __init__, __repr__ --- @dataclass generates them 
# automatically using type hints since Q & A are data types but choosing to override
# __eq__ to compare objects so keywords are excluded for now.

# Helper Function for csv reading (convert keyword columns from str back to lists) safely / automatically
def safe_eval(value_to_parse):
    """
    Safely evaluates a string representation of a Python literal, like a list.

    This function is designed to handle data from sources like CSVs where a
    list might be stored as a string (e.g., "['item1', 'item2']"). It uses
    `ast.literal_eval` for safe parsing, which only evaluates static literals
    and prevents the execution of arbitrary code.

    Args:
        value_to_parse (any): The value from the DataFrame cell to be parsed.

    Returns:
        list: A Python list if the input is a valid string representation of a list.
              An empty list is returned if the input is not a string (e.g., NaN).

    Raises:
        TypeError: If the input is a string but is malformed and cannot be
                   safely parsed into a Python literal (e.g., "['unclosed list").
    """
    # Check if it's a string first.
    if isinstance(value_to_parse, str):
        try:
            # If it's a valid string representation, return the parsed object as a list.
            return ast.literal_eval(value_to_parse)
        except (ValueError, SyntaxError) as e:
            # If parsing fails, raise an informative error. An entry other than a list (e.g. NaN, numberic) is unexpected /invalid.
            raise TypeError(f"Malformed string found in data column: '{value_to_parse}'") from e
    
    # If the value wasn't a string in the first place, treat it as an error (e.g. NaN or int would be invalid)
    raise TypeError(f"Expected a string to parse, but got {type(value_to_parse).__name__}.")


@dataclass(eq=False, frozen=True)
class Question:
    """Represents a single trivia question with its answer."""
    
    # Attributes are defined using type hints
    question_id: int 
    question_text: str
    correct_answer: str
    interrogative_keyword: List[str] = field(default_factory=list)  # Use default_factory for list/set/dict
    question_keywords: List[str] = field(default_factory=list)      # Use default_factory for list/set/dict
    answer_keywords: List[str] = field(default_factory=list)        # Use default_factory for list/set/dict
    session_id: Optional[int] = None                                # session specific id will be populated by Trivia class
    
    
    def __eq__(self, other):
        """Overrides @dataclass equality operator to compare question_id, question_text, and correct_answer to identify if question
        and answer are identical."""
        if isinstance(other, Question):
            # Reassess if should compare based on original ID, text, answer? Or just ID? consider in next phase
            return self.question_id == other.question_id and \
                   self.question_text == other.question_text and  \
                   self.correct_answer == other.correct_answer
        return NotImplemented
    
    def __str__(self):
        sess_id_str = f"[Session #{self.session_id}] " if self.session_id else ""
        return f"{sess_id_str}QID {self.question_id}: {self.question_text}\nAnswer: {self.correct_answer}" 
        
 
    # --- Public method for checking answer ---
    def check_answer(self, player_answer: str) -> bool:
        """
        Checks if the player provided answer is correct (case-insensitive comparison).
        """
        # clean answer (strip, lower, remove punctuation)
        standardized_player_answer = ut.clean_input_string(player_answer)
        standardized_correct_answer= ut.clean_input_string(self.correct_answer)
        # add fuzzy answer checking once methods work well
        
        return standardized_player_answer == standardized_correct_answer

class Trivia:
    """
        Manages the loading and selection of trivia questions for a game session.

        This class acts as the central repository for trivia data within the game.
        It is responsible for:
        1. Locating and loading the complete set of trivia questions from a specified
        CSV file into an internal pandas DataFrame upon initialization via the
        `start()` method.
        2. Selecting a random subset of these questions (based on the
        `NUM_QUESTIONS_PER_SESSION` constant) to be used for a single game session.

        An instance of this class typically holds the questions for one round or
        gameplay session. The `start()` method must be called after instantiation
        to load the data and prepare the session questions.

        Attributes:
            data_csv_filename (str): The filename of the source CSV file containing
                                    all trivia questions. Provided during instantiation.
            data_csv_path (Optional[Path]): The resolved absolute path to the
                                            `data_csv_filename`. Set by `_load_dataset()`.
                                            Defaults to None before `start()` is called.
            trivia_df (Optional[pd.DataFrame]): A pandas DataFrame holding the *entire*
                                                collection of trivia questions loaded
                                                from the CSV file. Set by `_load_dataset()`.
                                                Defaults to None before `start()` is called.
                                                May be large depending on the dataset size.
            questions (Optional[List[Dict[str, any]]]): A list containing the subset of
                                                        questions selected for the current
                                                        game session. Each question is
                                                        represented as a dictionary. Set by
                                                        `_load_questions()`. Defaults to None
                                                        before `start()` is called.
                                                        The structure of the dict depends
                                                        on the CSV columns.

        Methods:
            start(): Initializes the trivia session by loading the dataset and
                    selecting the session questions. This must be called before
                    accessing the `questions` attribute for gameplay.
        """
    def __init__(self,csv_filename: str):
        # Define at Trivia instance to correct version
        self.data_csv_filename = csv_filename  
        # These parameters will be set during game start @load
        self.data_csv_path =  None  
        self.trivia_df = None
        self.questions: Optional[List[Question]] = None 
        
    def __str__(self):
        """Return string summary of the Trivia session."""
        
        # --- Source File ---
        data_str = f"Source File: {self.data_csv_filename}"
        
        # --- Dataset Loading Status ---
        if self.data_csv_path and isinstance(self.data_csv_path, Path):
            # Show only last part of path if it's very long for readability
            path_repr = f"...{str(self.data_csv_path)[-50:]}" if len(str(self.data_csv_path)) > 50 else str(self.data_csv_path)
            status_str = f"Dataset Path: {path_repr}"
        else:
            status_str = "Dataset Status: Not loaded"
            
        # --- Full DataFrame Status ---
        if self.trivia_df is not None and isinstance(self.trivia_df, pd.DataFrame):
            df_status_str = f"Full Dataset Size: {len(self.trivia_df)} questions"
        else:
            df_status_str = "Full Dataset DataFrame: Not available" # More informative than 'not created'
        
        # --- Session Questions Status (Handles List[Question]) ---
        if self.questions is not None:
            q_count = len(self.questions)
            questions_status_str = f"Session Questions Ready: {q_count} questions"
        else:
            questions_status_str = "Session Questions: Not prepared"
        
        # --- Assemble the message ---
        str_message = [
            "--- Trivia Session Status ---",
            data_str,
            status_str,
            df_status_str,
            questions_status_str,
            "-----------------------------",
        ]
        return "\n".join(str_message)

    def _load_dataset(self):
        """
        Finds, loads, validates, and cleans the trivia dataset bundled with the package.

        This method performs a complete data loading pipeline:
        1.  Locates the data CSV file inside the installable package using `importlib.resources`.
        2.  Reads the CSV into a pandas DataFrame.
        3.  Validates the DataFrame to ensure it is not empty and contains all required columns.
        4.  Cleans the data by converting stringified list columns (e.g., 'question tokens')
            into actual Python lists using the `safe_eval` helper function and numbers a standard
            python int type.
        5.  Performs a final cross-check to validate that all columns have the expected Python data types.
        
        The final, clean DataFrame is stored in the `self._trivia_df` attribute.

        Raises:
            IOError: If the data file cannot be found, read, or accessed due to
                    file system or permission issues.
            ValueError: If the data file is empty, missing required columns,
                        or contains malformed data that cannot be parsed.
            TypeError: If a data column has an unexpected data type after cleaning.
        """
        # Expected schema
        expected_schema = {
            'original_question_id': int,
            'question': str,
            'answer': str,
            'interrogative_keyword': list,
            'question tokens': list,
            'answer tokens': list
        }
        
        try:
            # 1. Find and read data csv file. 
            # Finds the 'data' sub-package within 'HPtrivia_game' and get the csv file.
            pkg_data_path = resources.files('HPtrivia_game.data').joinpath(self.data_csv_filename)
            
            # 2. Use the .open() method to read it directly into pandas.
            with pkg_data_path.open('r', encoding='utf-8') as f:
                raw_df = pd.read_csv(f)
                self.data_csv_path = Path(str(pkg_data_path)) # Store the path
                
            # 2. validate df
            # make sure it isn't empty
            if raw_df.empty:  
                raise ValueError("The trivia data file is empty.")
            
            # if there are ANY NaN values anywhere in the entire DataFrame.
            if raw_df.isnull().values.any():
                raise ValueError("Data validation failed. The data file contains missing or null (NaN) values.")
        
            # it has all the expected columns
            expected_cols = set(expected_schema.keys())        
            if not expected_cols.issubset(set(raw_df.columns)):
                missing = expected_cols - set(raw_df.columns)
                raise ValueError(f"Data validation failed. The following required columns are missing from the datafile: {missing}")

            # 3. Clean and convert the columns back to correct, expected data type.
                # Explicitly convert the ID column to a standard Python integer type.
                # to ake sure there is no confusion of int and np int64 going forward.
            raw_df['original_question_id'] = raw_df['original_question_id'].apply(int)
            
                # convert the keywords columns to lists using helper function
            list_like_columns = ['interrogative_keyword', 'question tokens', 'answer tokens']
            for col in list_like_columns:
                if col in raw_df.columns:
                    raw_df[col] = raw_df[col].apply(safe_eval)

            # 4. Assign the validated, clean dataframe to the Trivia object
            self.trivia_df = raw_df[list(expected_schema.keys())]  # use keys to preserve column order           
        
        except (FileNotFoundError, PermissionError) as exc:
            raise IOError(f"Could not access data file '{self.data_csv_filename}'. Details: {exc}") from exc
        except (EmptyDataError, ParserError, ValueError, TypeError) as exc:
            raise ValueError(f"Data validation failed for '{self.data_csv_filename}'. Details: {exc}") from exc
        except Exception as exc: # General catch-all
            raise RuntimeError(f"An unexpected error occurred while loading the dataset: {exc}") from exc
  
    def _load_questions(self, num_questions_to_load):
        """
        Loads a random subset of trivia questions for the session.

        :raises ValueError: If the trivia dataset is not loaded.
        """
        # Ensure the dataset is loaded
        if self.trivia_df is None:
            raise ValueError("trivia_df is not loaded. Call _load_dataset() first.")
        
        # Select n random questions from the loaded DataFrame
        session_df = self.trivia_df.sample(
            n = num_questions_to_load,
            random_state=26,
            axis=0,
            replace=False
        )
        # Convert session questions from df to dictionary for fast lookup
        sessions_questions_dict = session_df.to_dict(orient='records')  # orient='records' gives list of dicts - keys are the column names.
        return sessions_questions_dict
    
    # Helper to convert dicts to Question objects 
    def _create_question_objects(self, question_dicts: Sequence[dict]):
        """
        Converts dicts to Question objects, adding session IDs and handling parsing.
        """
        question_objects = []
        for i, q_dict in enumerate(question_dicts):
                # Create the Question object
            q_obj = Question(
                session_id=i + 1, # Assign the 1-based session sequence ID
                question_id=q_dict['original_question_id'], 
                question_text=q_dict['question'],
                correct_answer=q_dict['answer'],
                interrogative_keyword = q_dict['interrogative_keyword'],
                question_keywords = q_dict['question tokens'],
                answer_keywords = q_dict['answer tokens']
                )
            question_objects.append(q_obj)

        return question_objects
    
    def get_session_questions(self) -> List[Question]:
        """
        Public method to safely provide the list of session questions.
        """
        # Make sure the game has started
        if self.questions is None:
            print("Warning: questions requested before they were loaded.")
            return [] # Return an empty list if not ready
        return self.questions
    
    def start(self, num_questions_to_load: int):
        """Initializes the trivia session by loading data and selecting questions.

        This method orchestrates the necessary steps to prepare the Trivia
        instance for a game session. It performs the following actions in order:

        1. Calls the internal `_load_dataset()` method: This finds the CSV
        file (specified by `self.data_csv_filename` during object creation)
        and loads its entire content into the `self.trivia_df` pandas
        DataFrame. It also sets `self.data_csv_path`.

        2. Calls the internal `_load_questions()` method: This selects a random
        subset of questions from the loaded `self.trivia_df` based on the
        `NUM_QUESTIONS_PER_SESSION` constant. The selected questions are
        stored as a list of dictionaries in the `self.questions` attribute.

        This method should typically be called once after the `Trivia` object
        is instantiated and before the game attempts to retrieve questions
        from the `self.questions` attribute.

        Side Effects:
            - Populates `self.data_csv_path` with the `Path` object of the loaded CSV.
            - Populates `self.trivia_df` with the complete DataFrame from the CSV.
            - Populates `self.questions` with the list of question dictionaries
            for the current session.

        Raises:
            FileNotFoundError: If the CSV file specified during instantiation
                            cannot be found by `_load_dataset`.
            pd.errors.EmptyDataError: If the found CSV file is empty (raised by
                                    `_load_dataset` via pandas).
            pd.errors.ParserError: If the CSV file is malformed (raised by
                                `_load_dataset` via pandas).
            ValueError: If `NUM_QUESTIONS_PER_SESSION` is greater than the total
                        number of questions available in the loaded dataset
                        (raised by `_load_questions`).
            Exception: Other potential exceptions related to file system access
                    or internal utilities used by the helper methods.
        """
        # Input validation:
        if not isinstance(num_questions_to_load, int):
            raise TypeError(f"Input 'num_questions_to_load' must be an integer, not {type(num_questions_to_load).__name__}.")
        if num_questions_to_load <= 0:
            raise ValueError("Invalid number of questions for the session. The number of questions needed to be greater than 0.")
        if num_questions_to_load > const.MAX_QUESTIONS_PER_SESSION:
            raise ValueError(f"Invalid number of questions for the session. A maximum of {const.MAX_QUESTIONS_PER_SESSION} questions are allowed.")
        
        # Load csv file:
        self._load_dataset()
        
        # guard clauses
        if self.trivia_df is None:
            raise ValueError("DataFrame was not loaded. Cannot proceed with setup.")
        
        if num_questions_to_load > len(self.trivia_df):
            raise ValueError(
                f"Not enough questions in the dataset ({len(self.trivia_df)}) "
                f"to load the requested {num_questions_to_load}."
        )
       
        # Load session n random questions and anwers
        questions_dict = self._load_questions(num_questions_to_load)
        # Confirmation message
        self.questions = self._create_question_objects(questions_dict) 

    def get_session_report_data(self) -> List[Dict[str, Any]]:
        """
        Generates a list of dictionaries containing details of the questions
        used in the current session for troubleshooting in cases errors spotted
        in trivia questions and anwers.
        """
        session_questions = self.get_session_questions()

        report_data = []
        for q_object in session_questions:
            report_data.append({
                "session_id": q_object.session_id,
                "original_question_id": q_object.question_id,
                "question_text": q_object.question_text,
                "correct_answer": q_object.correct_answer
            })
        return report_data
