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
from typing import List, Optional
from collections.abc import Sequence
import pandas as pd


# --- NO NEED TO MANUALLY WRITE __init__, __repr__ --- @dataclass generates them 
# automatically using type hints since Q & A are data types but choosing to override
# __eq__ to compare objects so keywords are excluded for now.

@dataclass(eq=False, frozen=True)
class Question:
    """Represents a single trivia question with its answer."""
    
    # Attributes are defined using type hints
    question_id: int 
    question_text: str
    correct_answer: str
    question_keyword: str
    question_keywords: List[str] = field(default_factory=list)  # Use default_factory for list/set/dict
    answer_keywords: List[str] = field(default_factory=list)    # Use default_factory for list/set/dict
    session_id: Optional[int] = None                            # session specific id will be populated by Trivia class
    
    
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
        # add fuzzy answer checking once methods work well
        return player_answer.strip().lower() == self.correct_answer.strip().lower()

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
        # if self.questions is not None: # Checks if the list object exists (was assigned)
        #     q_count = len(self.questions)
        #     # Report the count and type
        #     questions_status_str = f"Session Questions Ready: {q_count} (List[Question])"
        # else:
        #     questions_status_str = "Session Questions: Not prepared"
        
        # --- Assemble the message ---
        str_message = [
            "--- Trivia Session Status ---",
            data_str,
            status_str,
            df_status_str,
            # questions_status_str,
            "-----------------------------",
        ]
        return "\n".join(str_message)
    
    def _load_dataset(self):
        """Finds and loads the trivia dataset from a specified CSV file.

        This method searches for the CSV file whose name is stored in
        `self.data_csv_filename`. The search starts from a predefined
        root directory ('project_datasets') using the external utility
        `utils.utils_paths.find_file_path`.

        Upon successfully locating the file, its path is stored in
        `self.data_csv_path`, and its contents are loaded into a pandas
        DataFrame stored in `self.trivia_df`.

        Side Effects:
            Sets `self.data_csv_path` to the `Path` object of the found CSV file.
            Sets `self.trivia_df` to a pandas DataFrame containing the loaded data.

        Raises:
            FileNotFoundError: If the CSV file specified by `self.data_csv_filename`
                                cannot be found within the search directory, or if the
                                path found by `find_file_path` is invalid for `pd.read_csv`.
            pd.errors.EmptyDataError: If the found CSV file is empty.
            pd.errors.ParserError: If the CSV file is malformed and cannot be parsed by pandas.
            Exception: Potentially other exceptions raised by the
                        `utils.utils_paths.find_file_path` utility during the file search.
        """
        try:
            # Finds the 'data' sub-package within 'HPtrivia_game' and get the csv file.
            pkg_data_path = resources.files('HPtrivia_game.data').joinpath(self.data_csv_filename)
            
            with resources.as_file(pkg_data_path) as filepath:
                print(f"DEBUG: Loading bundled data from: {filepath}")
                self.data_csv_path = filepath
                self.trivia_df = pd.read_csv(filepath)

        except FileNotFoundError:
            # This error will be raised if the filename doesn't exist in the data package
            raise FileNotFoundError(f"Data file '{self.data_csv_filename}' not found within the package.")
        except Exception as e:
            raise IOError(f"Error reading bundled data file: {e}")
        
        # convert csv to data frame
        df = pd.read_csv(self.data_csv_path)
        # filter the relavent columns for the sessoin
        df = df[['original_question_id','question','answer','interrogative_keyword', 'question tokens', 'answer tokens']]
        
        self.trivia_df = df
        
        
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
    
    # --- Helper to convert dicts to Question objects ---
    def _create_question_objects(self, question_dicts: Sequence[dict]):
        """
        Converts dicts to Question objects, adding session IDs and handling parsing.
        """
        question_objects = []
        for i, q_dict in enumerate(question_dicts):
            try:
                # Example: Parse keywords if they are stored as comma-separated string in CSV/dict
                question_keywords_list = []
                answer_keywords_list = []
                # Map target lists and CSV column names
                keyword_mappings = [
                    ('question_keywords_list', 'question tokens'),
                    ('answer_keywords_list', 'answer tokens')]
                
                for list_name, token_column in keyword_mappings:
                    kw_data = q_dict.get(token_column)
                    if isinstance(kw_data, str):
                        parsed_list = [k.strip() for k in kw_data.split(',') if k.strip()]
                    elif isinstance(kw_data, list):
                        parsed_list = kw_data
                    else:
                        parsed_list = []

                    if list_name == 'question_keywords_list':
                        question_keywords_list = parsed_list
                    else:
                        answer_keywords_list = parsed_list
                
                  # Create the Question object
                q_obj = Question(
                    session_id=i + 1, # Assign the 1-based session sequence ID
                    question_id=int(q_dict['original_question_id']), 
                    question_text=str(q_dict['question']),
                    correct_answer=str(q_dict['answer']),
                    question_keyword = str(q_dict['interrogative_keyword']),
                    question_keywords = question_keywords_list,
                    answer_keywords = answer_keywords_list
                  )
                
                question_objects.append(q_obj)
                
            except KeyError as e:
                print(f"[Trivia._create_question_objects Warning] Missing expected key {e} in dict: {q_dict}. Skipping question.")
            except ValueError as e:
                print(f"[Trivia._create_question_objects Warning] Type conversion error for dict {q_dict}: {e}. Skipping question.")
            except Exception as e: # Catch broader errors during instantiation
                print(f"[Trivia._create_question_objects Warning] Unexpected error creating Question from dict {q_dict}: {e}. Skipping question.")

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
    
        # Load csv file:
        self._load_dataset()
        # Load session n random questions and anwers
        questions_dict = self._load_questions(num_questions_to_load)
        # Confirmation message
        self.questions = self._create_question_objects(questions_dict) 
        print(f"DEBUG: Trivia started. Loaded {len(self.questions) if self.questions else 0} questions for the session.") # Example log


