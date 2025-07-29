"""
Unit tests for the Trivia class and its methods in the HPtrivia_game package.
"""

# pylint: disable=redefined-outer-name, protected-access
from unittest.mock import patch
import pytest
import pandas as pd
from pandas.errors import ParserError
import numpy as np
from HPtrivia_game.trivia_manager import Trivia, Question

## --- FIXTURES ---
# Mocking and using fixture for repeated external dependencies
# i.e. triva dataset csv file and trivia dataset file path

# Fixture 1: File name
@pytest.fixture
def mock_filename() -> str:
    """A fixture that provides a consistent fake filename for tests."""
    return "fake_file.csv"

# Fixture 2: raw_df from csv
@pytest.fixture
def raw_df_fixture() -> pd.DataFrame:
    """Provides a raw DataFrame, simulating data as read directly from a CSV."""
    raw_data = {
        'original_question_id': [101, 102, 103],
        'question': ['Q1', 'Q2', 'Q3'],
        'answer': ['A1', 'A2', 'A3'],
        'interrogative_keyword': ["['what']", "['who']", "['where']"],
        'question tokens': ["['q1']", "['q2']", "['q3']"],
        'answer tokens': ["['a1']", "['a2']", "['a3']"]
    }
    return pd.DataFrame(raw_data)

## --- TESTS ---

## --- 1. Test for the __str__() method ---
# Test plan for str method:
#    1. Initial state: right after __init__() is called,
#    2. Partial loading state: after load_dataset() is called,
#    3. Full loading state: after start() is called and questions are loaded -> HAPPY PATH :)

# STATE 1: instantiate the Trivia object using the csv filename
def test_trivia_str_at_initialization(mock_filename: str):
    """Tests the string representation of a Trivia object in its initial state."""
    # Arrange: Create a new instance
    trivia = Trivia(mock_filename)
    # Act: Get the string representation
    output_str = str(trivia)
    # Assert: Check for the "not loaded" messages
    assert f"Source File: {mock_filename}" in output_str
    assert "Dataset Status: Not loaded" in output_str
    assert "Full Dataset DataFrame: Not available" in output_str
    assert "Session Questions: Not prepared" in output_str

# STATE 2: load the dataset (read csv, convert to a validated df, and assign to Trivia object)
#          This method inherently tests _load_dataset() method.

# General note on using patches:
# ------------------------------
# The @patch decorators automatically pass in mock objects as arguments to the
# test function, from the bottom decorator up.
# The two @patch decorators intercept the two separate file system calls:
# 1. The 'resources.files' patch silences the file *finding* step to prevent a FileNotFoundError.
# 2. The 'pd.read_csv' patch intercepts the file *reading* step.
# This allows the test to configure the mock_read_csv object to return the fake DataFrame from
# the fixture.

# NOTE: The _mock_resources parameter is required to catch the mock
#       provided by the resources @patch decorator, even though it's not used
#       in the specific test's logic.

@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_trivia_str_after_data_load(mock_read_csv, 
                                    _mock_resources,
                                    mock_filename,
                                    raw_df_fixture):
    """
    Tests the __str__ output after _load_dataset has been called.
    """
    # ARRANGE:
    # configure the mocks to simulate a successful file read.
    mock_read_csv.return_value = raw_df_fixture
    # create the Trivia instance.
    trivia = Trivia(mock_filename)

    # ACT: run the _load_dataset method only 
    trivia._load_dataset()
    output_str = str(trivia) # state 2 str()

    # ASSERT
    # check that the __str__ output correctly reflects state 2.
    assert "Dataset Path:" in output_str
    assert f"Full Dataset Size: {len(raw_df_fixture)} questions" in output_str
    assert "Session Questions: Not prepared" in output_str # questions are not yet loaded.

# STATE 3: (Also "Happy Path" for the full start() method)
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_start_method_fully_processes_data(mock_read_csv,
                                           _mock_resources,
                                           mock_filename,
                                           raw_df_fixture):
    """
    Tests that the start() method correctly finds, reads, cleans, and converts
    the raw data into a final list of Question objects.
    """
    # ARRANGE
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)

    # ACT: Run the entire start process. This will call _load_dataset (which does the cleaning)
    # and then _load_questions and _create_question_objects.
    trivia.start(num_questions_to_load=3)

    # ASSERT
    # Get the final product: the list of Question objects.
    final_questions = trivia.get_session_questions()
    # using a "random_state=26" in the _load_questions() for sample testing
    assert len(final_questions) == 3
    assert isinstance(final_questions[0], Question)
    # Check that the data inside the object is now the CORRECT, CLEANED type
    assert final_questions[0].question_id == 103
    assert isinstance(final_questions[0].interrogative_keyword, list)
    assert final_questions[0].interrogative_keyword == ['where']

## --- 2. Raw dataset integrity  ---
# Check if "gatekeeper" i.e. `_load_dataset()` is doing it's job
# NOTE: testing with _load_dataset() because it is the gatekeeper for all subsequent
# helpers which rely on it so need to catch errors as close to source.

# Test: the csv file cannot be found
@patch('HPtrivia_game.trivia_manager.resources.files')
def test_load_dataset_raises_ioerror_if_file_not_found(mock_resources_files):
    """
    Tests that _load_dataset raises an IOError if the CSV file cannot be found.
    """
    # ARRANGE
    # Configure the mock to raise an error when called, simulating a missing file.
    mock_resources_files.side_effect = FileNotFoundError("Simulated file not found")
    
    trivia = Trivia("a_missing_file.csv")

    # ACT & ASSERT
    # Assert that calling the method now results in the IOError we expect.
    with pytest.raises(IOError, match="Could not access data file"):
        trivia._load_dataset()

# Test: raw dataset is corrupted
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_load_dataset_raises_valueerror_if_csv_is_corrupted(mock_read_csv, _mock_resources):
    """
    Tests that _load_dataset raises a ValueError if pandas cannot parse the file.
    """
    # ARRANGE: configure the pd.read_csv mock to raise a ParserError, simulating a corrupt file.
    mock_read_csv.side_effect = ParserError("Simulated CSV parsing error")
    trivia = Trivia("any_corrupt_file.csv")

    # ACT & ASSERT
    # Assert results in the ValueError from the try/except block.
    with pytest.raises(ValueError, match="Data validation failed"):
        trivia._load_dataset()        

# Test: raw dataset is empty
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_raw_data_is_empty(mock_read_csv,
                                _mock_resources,
                                mock_filename):
    """
    Tests that the data loading process raises a ValueError if the csv is empty
    """
    # ARRANGE
    bad_df = pd.DataFrame() 
    mock_read_csv.return_value = bad_df
    trivia = Trivia(mock_filename)

    # ACT & ASSERT
    with pytest.raises(ValueError, match="The trivia data file is empty"):
        trivia._load_dataset()

# Test: dataset is missing one of the critical columns, e.g. 'question' 
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_raw_data_is_missing_question_column( mock_read_csv,
                                                  _mock_resources,
                                                   mock_filename, 
                                                   raw_df_fixture):
    """
    Tests that the data loading process raises a ValueError if a required
    column like 'question' is missing from the source data.
    """
    # ARRANGE
    bad_df = raw_df_fixture.drop(columns=['question'])
    mock_read_csv.return_value = bad_df
    trivia = Trivia(mock_filename)

    # ACT & ASSERT
    with pytest.raises(ValueError, match="The following required columns are missing"):
        trivia._load_dataset()

# Test: dataset columns are missing entries -> None or NaN (critical)
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_raw_data_columns_have_nans( mock_read_csv,
                                         _mock_resources,
                                          mock_filename,
                                          raw_df_fixture):
    """
    Tests that the data loading process raises a ValueError if a required
    column like 'question' is missing entries (NaN present).
    """
    # ARRANGE
    bad_df = raw_df_fixture.copy()
    # introduce the NaNs
    bad_df.loc[1, 'question'] = np.nan
    bad_df.loc[0, 'answer'] = np.nan
    bad_df.loc[2, 'question tokens'] = np.nan
    mock_read_csv.return_value = bad_df
    trivia = Trivia(mock_filename)
    
    # Act and Assert
    with pytest.raises(ValueError, match="Data validation failed"):
        trivia._load_dataset()

# Test: dataset column formatting: raw data not matching expected data schema
# int type
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_raw_data_column_are_correct_data_types( mock_read_csv,
                                                     _mock_resources,
                                                      mock_filename,
                                                      raw_df_fixture):
    """
    Tests that _load_dataset raises a ValueError if a column contains
    data that cannot be converted to the correct type.
    """
    # ARRANGE
    bad_df = raw_df_fixture.copy()
    # change column type from int to object to allow insertion of "error" for 
    # testing (ie. mixed data types)
    bad_df['original_question_id'] = bad_df['original_question_id'].astype(object)
    # introduce the NaNs
    bad_df.loc[1, 'original_question_id'] = "not-a-number"
    mock_read_csv.return_value = bad_df
    trivia = Trivia(mock_filename)

    # Act and Assert
    with pytest.raises(ValueError, match="Data validation failed"):
        trivia._load_dataset()

# stringified list        
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_load_dataset_raises_error_on_malformed_list_string(mock_read_csv,
                                                            _mock_resources,
                                                            raw_df_fixture):
    """
    Tests that _load_dataset raises a ValueError if a keyword column contains
    a malformed string that cannot be parsed into a list.
    """
    # ARRANGE
    # 1. Take the standard raw data and make a copy.
    bad_df = raw_df_fixture.copy()

    # 2. Intentionally corrupt the data with an unclosed bracket.
    bad_df.loc[0, 'interrogative_keyword'] = "['what'"

    # 3. Configure the mock to return this corrupted DataFrame.
    mock_read_csv.return_value = bad_df

    trivia = Trivia("any.csv")

    # ACT & ASSERT
    # 4. Assert that calling _load_dataset now raises a ValueError.
    with pytest.raises(ValueError, match="Data validation failed"):
        trivia._load_dataset()        

## --- 3. Failure or edge cases ---
# _load_question() operation

# Test: sampling correctly if the number of questions to load and df size are the samme
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_questions_sampling_when_loading_all_questions(mock_read_csv,
                                                       _mock_resources,
                                                       mock_filename,
                                                       raw_df_fixture):
    """
    Tests that start() correctly samples all questions when the requested number
    equals the total number available in the dataset.
    """
    # ARRANGE
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)
    num_to_load = len(raw_df_fixture)  # using max length of df to keep code dynamic.

    # ACT 
    trivia.start(num_questions_to_load=num_to_load)

    # ASSERT
    final_questions = trivia.get_session_questions()
    #1. confirm the size
    assert len(final_questions) == len(raw_df_fixture)

    #2. confirm content 
    # get the fixture ids to test against (order is preserved here)
    original_ids = raw_df_fixture['original_question_id']
    # final_ids are random from sampling but also from the 'set' comprehension 
    # to get the id_attribute of each Question ojbect (q) in the List of Questions.
    final_ids = {q.question_id for q in final_questions}
    assert set(original_ids) == final_ids # confirms content is equivalent irrespective of order.

# trivia_df doesn't exist (_load_dataset() not called)
def test_load_question_called_but_no_dataframe_assigned(mock_filename):
    """
    Tests that _load_questions raises a ValueError if called before
    _load_dataset (i.e., when self.trivia_df is None)
    """
    # ARRANGE
    trivia = Trivia(mock_filename)
    # without a call for _load_dataset(), trivia.trivia_df is None

    # ACT & ASSERT
    # Need escape chars for brackets to match the regex pytest uses to check string pattern.
    with pytest.raises(ValueError, 
                       match="trivia_df is not loaded. Call _load_dataset\\(\\) first."):
        trivia._load_questions(num_questions_to_load = 1)

##--- 4. Failure or edge cases for _create_question_objects() ---

# the method recieves an empty list
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_if_create_question_object_gets_empty_list(mock_read_csv,
                                                   _mock_resources,
                                                   mock_filename,
                                                   raw_df_fixture):
    """
    Tests that _create_question_objects correctly handles an empty list
    and returns an empty list without crashing (e.g. num_to_load = 0)
    """
    # Arrange
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)
    questions_dict = []

    # Act
    session_questions = trivia._create_question_objects(questions_dict)

    # Assert
    assert session_questions ==[]

# check if the sequential session_ids are assigned correctly
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_session_in_question_objects_list(mock_read_csv,
                                          _mock_resources,
                                          mock_filename,
                                          raw_df_fixture):
    """
    Test that _create_question_object correctly add sequential ids 
    to each Question object when preparing the list for game play.
    """
    # Arrange
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)
    num_to_load = len(raw_df_fixture)  # using max length of df to keep code dynamic.

    # Act
    trivia.start(num_questions_to_load=num_to_load)
    session_questions = trivia.get_session_questions()

    # Assert
    # create a list of actual ids using list comprehension
    actual_ids = [q.session_id for q in session_questions]
    expected_ids = list(range(1,num_to_load+1,1))

    assert actual_ids == expected_ids

##--- 5. Failure or edge cases for get_session_questions() ---
# simple public getter - so check happy path and empty input

# If it recieves an empty list of Questions
def test_get_session_questions_returns_empty_list_when_not_loaded(mock_filename):
    """
    Tests that get_session_questions returns an empty list if start() has not been called.
    """
    #Arrange
    trivia = Trivia(mock_filename)
    #Act
    questions = trivia.get_session_questions()
    #Assert
    assert questions == []

# Happy path: called after start and has the list
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_get_session_questions_returns_list_of_questions_after_start(mock_read_csv,
                                                                     _mock_resources,
                                                                     mock_filename,
                                                                     raw_df_fixture):
    """
    Tests that get_session_questions returns a list of Question objects
    after a successful run.
    """
    # Arrange
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)

    #Act
    trivia.start(num_questions_to_load=len(raw_df_fixture))
    test_questions = trivia.get_session_questions()

    #Assert
    assert len(test_questions) == len(raw_df_fixture)
    assert isinstance(test_questions, list)
    assert isinstance(test_questions[0], Question)

##--- 6. Failure or edge cases for get_session_report_data() ---
# the second public getter - so check happy path and empty input

# If it recieves an empty list from get_session_questions
def test_get_session_report_returns_empty_dict_when_not_loaded(mock_filename):
    """
    Tests that get_session_report_data returns an empty list if start() has not been called.
    """
    # Arrange
    trivia = Trivia(mock_filename)
    #Act
    test_report = trivia.get_session_report_data()
    #Arrange
    assert test_report == []

# Happy path
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_get_session_report_returns_reportdata_after_start(mock_read_csv,
                                                           _mock_resources,
                                                           mock_filename,
                                                           raw_df_fixture):
    """
    Tests that get_session_report_data returns a list of question dicts 
    after a successful run.
    """
    #Arrange
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)

    # Act
    trivia.start(num_questions_to_load=len(raw_df_fixture))
    test_report = trivia.get_session_report_data()

    #Arrange
    assert isinstance(test_report, list)
    assert isinstance(test_report[0], dict)
    assert len(test_report) == len(raw_df_fixture)

    first_question = test_report[0]
    # based on random_seed = 26
    assert first_question['session_id'] == 1
    assert first_question['original_question_id'] == 103
    assert first_question['question_text'] == 'Q3'
    assert first_question['correct_answer'] == 'A3'

##--- 7. Failure or edge cases for start() ---

# Input validation: main input is num_questions_to_load

# Test: the provided number_of_questions to load is not `int` type
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_question_num_is_not_an_int(mock_read_csv,
                                         _mock_resources,
                                         mock_filename, 
                                         raw_df_fixture):
    """
    Tests that start() raises a ValueError if requesting the number of 
    questions is not of type `int`.
    """
    # ARRANGE
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)
    num_to_load = 3.5

    # ACT & ASSERT
    with pytest.raises(TypeError, match="Input 'num_questions_to_load' must be an integer"):
        trivia.start(num_questions_to_load=num_to_load) # pyright: ignore
        
# Test: requesting a invalid number of question (ie. 0, -1, str etc)
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_question_num_is_invalid(mock_read_csv,
                                      _mock_resources,
                                      mock_filename,
                                      raw_df_fixture):
    """
    Tests that start() raises a ValueError if requesting the number of 
    questions to load i an invalid number.
    """
    # ARRANGE
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)
    num_to_load = 0

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Invalid number of questions for the session"):
        trivia.start(num_questions_to_load=num_to_load)

# Test: requesting more than max number of questions allowed
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_question_num_is_greater_than_max_limit(mock_read_csv,
                                                     _mock_resources,
                                                     mock_filename,
                                                     mocker,
                                                     raw_df_fixture):
    """
    Tests that start() raises a ValueError if the number of requested questions
    exceeds the MAX_QUESTIONS_PER_SESSION constant
    """
    # ARRANGE
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)
    num_to_load = len(raw_df_fixture)  # using max length of df to keep code dynamic.
    # Mock max questions will always be one less to guarantee the request will be over limit.
    mocker.patch('HPtrivia_game.constants.MAX_QUESTIONS_PER_SESSION', num_to_load-1)

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Invalid number of questions for the session. A maximum"):
        trivia.start(num_questions_to_load=num_to_load)

# Transtions: after _load_data is succesful, before _load_questions
# Test: if _load_dataset returns and empty df
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_start_raises_error_when_dataset_is_empty(mock_read_csv, _mock_resources):
    """
    Tests that start() raises a ValueError if the loaded CSV file is empty.
    """
    # ARRANGE
    mock_read_csv.return_value = pd.DataFrame() # empty df
    
    # 2. Create the Trivia instance.
    trivia = Trivia("any_empty_file.csv")

    # ACT & ASSERT
    # calling start() now raises the expected ValueErro because the df is empty.
    with pytest.raises(ValueError, match="The trivia data file is empty"):
        trivia.start(num_questions_to_load=3)

# Test: if Num questions to load is greater than available questions in df
@patch('HPtrivia_game.trivia_manager.resources.files')
@patch('HPtrivia_game.trivia_manager.pd.read_csv')
def test_when_question_num_is_greater_than_dataset_size(mock_read_csv,
                                                        _mock_resources,
                                                        mock_filename, 
                                                        raw_df_fixture):
    """
    Tests that start() raises a ValueError if requesting more questions than available.
    """
    # ARRANGE
    mock_read_csv.return_value = raw_df_fixture
    trivia = Trivia(mock_filename)
    num_to_load = 5

    # ACT & ASSERT
    with pytest.raises(ValueError, match="Not enough questions in the dataset "):
        trivia.start(num_questions_to_load=num_to_load)
