'''
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

CLI MVP (core logic) -> trivia module (data)

------------------------------------------------------------------

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
  
  '''
# Import necessary libraries:
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
import json
import pandas as pd
from HPtrivia_game.constants import NUM_QUESTIONS_PER_SESSION
import utils.utils_paths as up

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
        self.questions = None 
        
    def __str__(self):
        """Return string summary of the Trivia session."""
        
        data_str = f"The session trivia questions are from: {self.data_csv_filename}."
        # In case dataset hasn't been loaded:
        if self.data_csv_path:
            data_location_str = f"The session trivia dataset is located in: {self.data_csv_path}"
        data_location_str = "The session trivia dataset has not been loaded yet.\n"
         # In case dataframe isn't setup yet:
        if self.trivia_df is not None:
            dataframe_str = f"The head (top 5 rows) of the sesion trivia dataset is:\n{self.trivia_df.head()}"
        dataframe_str = "The session dataframe has not been created yet."
         # In case the session dictionary isn't setup yet:
        if self.questions:
            question_dict_str = f"The random questions and answers selected for this session are:\n {json.dumps(self.questions, indent=2)}"
        question_dict_str = "The random questions and answers set has not been collected yet."
        
        str_message = [
            "=== Trivia Session Summary ===",
            data_str,
            data_location_str,
            dataframe_str,
            question_dict_str,
            "-" * 30
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
        # return dataframe of full dataset
        search_root = Path("project_datasets")
        self.data_csv_path = up.find_file_path(self.data_csv_filename, search_root)
        self.trivia_df = pd.read_csv(self.data_csv_path)
        
    def _load_questions(self):
        """
        Loads a random subset of trivia questions for the session.

        :raises ValueError: If the trivia dataset is not loaded.
        """
        # Ensure the dataset is loaded
        if self.trivia_df is None:
            raise ValueError("trivia_df is not loaded. Call _load_dataset() first.")

        # Select n random questions from the loaded DataFrame
        session_df = self.trivia_df.sample(
            n=NUM_QUESTIONS_PER_SESSION,
            random_state=26,
            axis=0,
            replace=False
        )
        # Need to add question_id to dict as the key?
        # Convert session questions from df to dictionary
        self.questions = session_df.to_dict(orient='records')  # orient='records' gives list of dicts
    
    def start(self):
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
        self._load_questions()
        
#___________________________________________________________________________        

# --- NO NEED TO MANUALLY WRITE __init__, __repr__ --- @dataclass generates them automatically using 
# type hints since Q & A are data types but choosing to override __eq__ to compare objects so 
# keywords are excluded for now.

@dataclass(eq=False)
class Question:
    """Represents a single trivia question with its answer."""
    
    # 1. Define attributes using type hints
    question_id: int 
    question_text: str
    correct_answer: str

    # 2. Using field() for default mutable type
    keywords: List[str] = field(default_factory=list) # Use default_factory for list/set/dict

    def __eq__(self, other):
        """Overrides @dataclass equality operator to compare question_id, question_text, and correct_answer to identify if question
        and answer are identical."""
        if isinstance(other, Question):
            return self.question_id == other.question_id and \
                   self.question_text == other.question_text and  \
                   self.correct_answer == other.correct_answer
        return NotImplemented
    
    def __str__(self):
        return f"Question: {self.question_text},\nAnswer: {self.correct_answer},\nKeywords: {', '.join(self.keywords)}"
    
    def _prepare_question_to_ask(self):
        # Prepare the question for View class to ask player
        pass
  
    def _check_answer(self, player_answer: str) -> bool:
        """
        Checks if the player provided answer is correct by comparing it to the correct answer.
        """
        return player_answer.lower() == self.correct_answer.lower()
    