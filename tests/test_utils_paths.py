"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================
Manual Test Script for Project Path Utilities (utils_paths).

This script performs a series of manual tests on the functions defined in
the `utils_paths.py` module, including:
- `find_project_root`
- `get_data_folder_path`
- `find_file_path`
- `save_dataframe_to_csv`

It covers various scenarios such as:
- Valid ("happy path") execution.
- Handling of invalid inputs (None, empty strings, wrong types).
- Edge cases (invalid filename characters, empty DataFrames).
- Filesystem interactions (file/directory existence, non-existent paths).

The script includes automated setup (creating temporary directories/files
within the project's 'data/' structure) and cleanup (removing created artifacts)
to facilitate testing filesystem interactions reliably.

Usage:
------
Execute this script directly. Observe the printed output for each test case
(prefixed with '--- Test Case X.Y ---') to manually verify the actual outcome
against the expected behavior noted in the comments within the test case lists.

Note:
-----
- This script is intended for manual verification by observing print statements.
  It does not use a formal testing framework like pytest or unittest with assertions.
- As of 2025-04-22, it may contain commented-out output from previous test runs
  for historical diagnostic purposes.
- Ensure the required libraries (pandas, utils_paths) are available in the
  environment before running.
"""

from pathlib import Path
from typing import Optional
import shutil
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
import utils.utils_paths as up
# import test

test_csv_name = 'clean_trivia_dataset_v0.csv'

#----------------------------------------------------------------------
# 1. Test `up.find_project_root()` with different tests cases arguments for `start_path`
test_cases_start_root = [
    None,
    "tests/test_utils_paths.py",
    "src",
    Path("src"),
    "/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia",
    "nonexistent/file.py",
    "\0invalid"
]

for case in test_cases_start_root:
    try:
        print(f"Test 1. Input: {case!r} → Output: {up.find_project_root(case)}")
    except Exception as e:
        print(f"Test 1. Input: {case!r} → Error: {type(e).__name__}: {e}")


# Manual Test Summary:
# --------------------
# ✓ None → uses __file__ or CWD and found root correctly
# ✓ "tests/test_utils_paths.py" → worked as expected
# ✓ "src" → worked correctly by converting to Path
# ✓ Path("src") → worked correctly by recognizing it as Path type
# ✓ full path to root: worked correctly
# ✗ "nonexistent/path" → correctly raised FileNotFoundError
# ✗ "\0invalid" → correctly raised ValueError

#----------------------------------------------------------------------

# 2. Test `up.find_file_path()` with different subfolder / file strings

test_cases_ffp = [
    ("does_not_exist.csv", None),                   # 1. ❌ (No subfolder, incorrect filename) expect a FileNotFound error.
    (test_csv_name, None),                          # 2. ✅ (No subfolder, correct filename) expect to work
    (test_csv_name, "data"),                        # 3. ✅ (correct grandparent dir, correct filename) expect to work
    (test_csv_name, "src"),                         # 4. ❌ (incorrect dir, correct filename) expect a FileNotFound error.
    (test_csv_name, "random_folder"),               # 5. ❌ (non-existent dir, correct filename) expect a FileNotFound error.
    (test_csv_name, str(Path.cwd())),               # 6. ✅ (full path for substring, correct filename) expect to work.
    (test_csv_name, ""),                            # 7. ✅ (empty string for subfolder, correct filename) expect work same as None.
    ("project_datasets/" + test_csv_name, None),    # 8. ✅ (filepath with separators with parent dir, correct filename)- expect to work
    ("data/" + test_csv_name, None),                # 9. ❌ (filepath with separators with parent dir missing and using grandparent, correct filename)- Error, FileNotFound
    (test_csv_name, test_csv_name),                 # 10.❌ (Pass filename instead of path, correct filename) - Error, FileNotFound 
    (Path(test_csv_name), None),                    # 11.❌ (No subfolder, Path object for filename) - Error, (OsError catchall)
    (Path(test_csv_name), Path("data")),            # 12.❌ (Path objects for both filename and subfolder) - Error (OsError catchall)
    (Path.cwd() / "data" / test_csv_name, None)     # 13.❌ (No subfolder, Absolute Path as filename) - Error (OsError catchall)
]
i = 1
for name, subfolder in test_cases_ffp:
    try:
        print(f"✅ Test 2.{i}. → Output: {up.find_file_path(name,subfolder)}")
    # First pass manual testing - bypassing pylint warning for "Exception" is to generic for now.
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"❌ Test 2.{i}. → Error: {type(e).__name__}: {e}")
    i+=1
        
# Manual Test Summary: [Pass 1]
# --------------------
# ❌ Test 2.1. → Error: FileNotFoundError: File 'does_not_exist.csv' not found recursively under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia'.
# ✅ Test 2.2. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ✅ Test 2.3. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ❌ Test 2.4. → Error: FileNotFoundError: File 'clean_trivia_dataset_v0.csv' not found recursively under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/src'.
# ❌ Test 2.5. → Error: FileNotFoundError: Provided search root path is not an existing directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/random_folder
# ✅ Test 2.6. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ✅ Test 2.7. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ✅ Test 2.8. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ❌ Test 2.9. → Error: FileNotFoundError: File 'data/clean_trivia_dataset_v0.csv' not found recursively under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia'.
# ❌ Test 2.10. → Error: FileNotFoundError: Provided search root path is not an existing directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/clean_trivia_dataset_v0.csv
# ❌ Test 2.11. → Error: OSError: Error during file search for 'clean_trivia_dataset_v0.csv' under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia': 'PosixPath' object is not subscriptable
# ❌ Test 2.12. → Error: OSError: Error during file search for 'clean_trivia_dataset_v0.csv' under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data': 'PosixPath' object is not subscriptable
# ❌ Test 2.13. → Error: OSError: Error during file search for '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/clean_trivia_dataset_v0.csv' under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia': 'PosixPath' object is not subscriptable

# Tests 2.11 to 2.13 errors dealt by strict enforcement of input as strings. TypeError otherwise.
# Code has been updated to reflect this.
# TEST PASS 2

# ❌ Test 2.1. → Error: FileNotFoundError: File 'does_not_exist.csv' not found recursively under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia'.
# ✅ Test 2.2. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ✅ Test 2.3. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ❌ Test 2.4. → Error: FileNotFoundError: File 'clean_trivia_dataset_v0.csv' not found recursively under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/src'.
# ❌ Test 2.5. → Error: FileNotFoundError: Provided search root path is not an existing directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/random_folder
# ✅ Test 2.6. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ✅ Test 2.7. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ✅ Test 2.8. → Output: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/clean_trivia_dataset_v0.csv
# ❌ Test 2.9. → Error: FileNotFoundError: File 'data/clean_trivia_dataset_v0.csv' not found recursively under '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia'.
# ❌ Test 2.10. → Error: FileNotFoundError: Provided search root path is not an existing directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/clean_trivia_dataset_v0.csv
# ❌ Test 2.11. → Error: TypeError: Argument 'filename' must be a string, not PosixPath. (correctly caught as TypeError)
# ❌ Test 2.12. → Error: TypeError: Argument 'filename' must be a string, not PosixPath. (correctly caught as TypeError)
# ❌ Test 2.13. → Error: TypeError: Argument 'filename' must be a string, not PosixPath. (correctly caught as TypeError)

# #----------------------------------------------------------------------

# 3. Test `up.find_data_folder()` with different subfolder strings

subfolder_testcases = [
    '', # Default
    None,
    "project_datasets", # working folder
    "projects_datasets", # with a typo
    "original_dataset_DONT_TOUCH", # reference folder
    " ",
    "nonexistent_folder",
    "\0invalid"
]

for case in subfolder_testcases:
    try:
        print(f"Test 3. Input: {case!r} → Output: {up.get_data_folder_path(case)}")
    except Exception as e:
        print(f"Test 3. Input: {case!r} → Error: {type(e).__name__}: {e}")
    
# Manual Test Summary:
# --------------------
# ✓ Input: '' → Output correctly provides path to the data subdirectory
# ✗ Input: None → Error: TypeError: unsupported operand type(s) for /: 'PosixPath' and 'NoneType'
# ✓ Input: 'project_datasets' → Output correctly provides absolute path to the right directory
# ✗ Input: 'projects_datasets' → Output correctly responds with FileNotFoundError
# ✓ Input: 'original_dataset_DONT_TOUCH' → Output correctly provides absolute path to the right directory
# ✗ Input: ' ' → Correctly raises an Error: FileNotFoundError: Required data directory not found or is not a directory
# ✗ Input: 'nonexistent_folder' → Correctly raises an Error: FileNotFoundError: Required data directory not found or is not a directory
# ✗ Input: '\x00invalid' → Correctly raises an Error: FileNotFoundError: Required data directory not found or is not a directory


#======================================================================
#----------------------------------------------------------------------

# 4. Test `up.save_dataframe_to_csv()`: 

# --- Testing Context ---
# These tests validate the 'save_dataframe_to_csv' function.
# The function saves files relative to the project's 'data/' directory,
# using 'get_data_folder_path' internally.
# To ensure test isolation and simplify cleanup, most test outputs are
# directed into a temporary subdirectory within 'data/project_datasets/'.
# This temporary directory is created before tests and deleted afterwards.

print("--- Test Setup ---")
# Initialize variables to None for safer error handling in setup/cleanup
project_root: Optional[Path] = None
temp_test_output_subdir: Optional[Path] = None
file_as_subdir_path: Optional[Path] = None
test13_output_file: Optional[Path] = None

# Define constants for test parameters where needed
TEST_FILENAME_BASE = "test_output_file"
TEST_VERSION = "v_test"

try:
    # --- 1. Define Core Paths ---
    project_root = up.find_project_root()
    print(f"Project Root Found: {project_root}")
    data_dir = project_root / "data"
    project_datasets_dir = data_dir / "project_datasets"
    temp_test_output_subdir_name = "temp_test_outputs_delete_me"
    temp_test_output_subdir = project_datasets_dir / temp_test_output_subdir_name
    file_as_subdir_path_name = "subfolder_is_a_file_setup.txt"
    file_as_subdir_path = data_dir / file_as_subdir_path_name
    # Define path for Test 13 output (uses default subfolder)
    test13_output_file = project_datasets_dir / f"{TEST_FILENAME_BASE}_{TEST_VERSION}.csv"

    # --- 2. Perform Pre-Test Cleanup ---
    print("Cleaning up previous test artifacts if they exist...")
    if temp_test_output_subdir and temp_test_output_subdir.exists():
        shutil.rmtree(temp_test_output_subdir) # Remove entire temp output dir
    if file_as_subdir_path: file_as_subdir_path.unlink(missing_ok=True)
    if test13_output_file: test13_output_file.unlink(missing_ok=True)
    # Cleanup file potentially created by previous Test 14 runs directly in data/
    (data_dir / f"{TEST_FILENAME_BASE}_{TEST_VERSION}.csv").unlink(missing_ok=True)


    # --- 3. Create Fresh Test Environment ---
    if temp_test_output_subdir: # Check if var assigned before using mkdir
        temp_test_output_subdir.mkdir(parents=True, exist_ok=True)
        print(f"Created temporary test output directory: {temp_test_output_subdir.relative_to(project_root)}")
    # Ensure default dir exists (needed for test 13)
    project_datasets_dir.mkdir(parents=True, exist_ok=True)
    print(f"Ensured default data directory exists: {project_datasets_dir.relative_to(project_root)}")
    if file_as_subdir_path: # Check if var assigned before using touch
        file_as_subdir_path.touch(exist_ok=True)
        print(f"Created setup file for Test 16: {file_as_subdir_path.relative_to(project_root)}")
    print("Setup complete.")

except (FileNotFoundError, OSError, Exception) as setup_e:
    print("💥 CRITICAL SETUP ERROR: Could not find project root or setup test dirs/files.")
    print(f"Error: {type(setup_e).__name__}: {setup_e}")
    # Consider exiting if setup fails: exit()

# --- Test Data Definition ---
toy_df = pd.DataFrame({"Question": ["Q1"], "Answer": ["A1"]})
empty_df = pd.DataFrame()
# Using constants defined above for base filename/version
# Define the relative path string pointing to the temp dir
subfolder_param_for_temp_dir = f"project_datasets/{temp_test_output_subdir_name}"

# --- Test Case List Definition (for tests 3-16) ---
# This list will be iterated through using unique filenames for isolation
test_cases_for_loop = [
    # Dataframe Input Issues
    (None, TEST_FILENAME_BASE, TEST_VERSION, subfolder_param_for_temp_dir),       # 3. ❌ Expect error from pandas.
    ("", TEST_FILENAME_BASE, TEST_VERSION, subfolder_param_for_temp_dir),         # 4. ❌ Expect error from pandas.
    (10254, TEST_FILENAME_BASE, TEST_VERSION, subfolder_param_for_temp_dir),      # 5. ❌ Expect error from pandas.
    (empty_df, TEST_FILENAME_BASE, TEST_VERSION, subfolder_param_for_temp_dir),   # 6. ✅ Expect success saving empty file (unique name).
    # Filename_base Input Issues
    (toy_df, None, TEST_VERSION, subfolder_param_for_temp_dir),         # 7. ❌ Expect TypeError.
    (toy_df, "", TEST_VERSION, subfolder_param_for_temp_dir),           # 8. ✅ Expect success creating file like '_v_test_8.csv'.
    (toy_df, '@laj;/-', TEST_VERSION, subfolder_param_for_temp_dir),    # 9. ❌ Expect OSError/ValueError (invalid chars).
    # Version Input Issues
    (toy_df, TEST_FILENAME_BASE, None, subfolder_param_for_temp_dir),        # 10. ❌ Expect TypeError.
    (toy_df, TEST_FILENAME_BASE, "", subfolder_param_for_temp_dir),          # 11. ✅ Expect success creating 'test_output_file_11_.csv'.
    (toy_df, TEST_FILENAME_BASE, '@laj;/-', subfolder_param_for_temp_dir),   # 12. ❌ Expect OSError/ValueError (invalid chars).
     # Subfolder Parameter Issues
    (toy_df, TEST_FILENAME_BASE, TEST_VERSION, None),          # 13. ✅ Expect success saving to default 'project_datasets' (after fix).
    (toy_df, TEST_FILENAME_BASE, TEST_VERSION, ""),            # 14. ❌ Expect ValueError from get_data_folder_path (after fix).
    (toy_df, TEST_FILENAME_BASE, TEST_VERSION, "nonexistent_dir"), # 15. ❌ Expect FileNotFoundError from get_data_folder_path.
    (toy_df, TEST_FILENAME_BASE, TEST_VERSION, file_as_subdir_path_name) # 16. ❌ Expect FileNotFoundError from get_data_folder_path.
]

# --- Test Execution ---
print("\n--- Running save_dataframe_to_csv tests ---")

# --- Test 1: Create File in Temp Dir (Uses NON-unique name) ---
print("\n--- Test Case 4.1 (Create) ---")
print(f"Inputs: df=<DataFrame>, filename='{TEST_FILENAME_BASE}', version='{TEST_VERSION}', subfolder='{subfolder_param_for_temp_dir}'")
try:
    result1 = up.save_dataframe_to_csv(toy_df, TEST_FILENAME_BASE, TEST_VERSION, subfolder_param_for_temp_dir)
    print(f"✅ Test 4.1. → Output Type: {type(result1).__name__}, Output Value: {result1}")
except Exception as e:
    print(f"💥 Test 4.1. → UNEXPECTED Error: {type(e).__name__}: {e}")

# --- Test 2: Check Skip Logic for File in Temp Dir (Uses NON-unique name) ---
print("\n--- Test Case 4.2 (Skip) ---")
print(f"Inputs: df=<DataFrame>, filename='{TEST_FILENAME_BASE}', version='{TEST_VERSION}', subfolder='{subfolder_param_for_temp_dir}'")
try:
    result2 = up.save_dataframe_to_csv(toy_df, TEST_FILENAME_BASE, TEST_VERSION, subfolder_param_for_temp_dir)
    print(f"✅ Test 4.2. → Output Type: {type(result2).__name__}, Output Value: {result2}")
    if result2 is None: print("ℹ️  Info Test 4.2: Correctly returned None.")
    else: print(f"⚠️ WARNING Test 4.2: Expected None return but got {type(result2).__name__}")
except Exception as e:
    print(f"💥 Test 4.2. → UNEXPECTED Error: {type(e).__name__}: {e}")

# --- Loop through remaining tests (original cases 3 to 16) USING UNIQUE FILENAMES ---
i = 3 # Start index for remaining tests
for df_arg, fname_base_arg, vers_arg, subfolder_arg in test_cases_for_loop:
    print(f"\n--- Test Case 4.{i} ---")

    # --- Generate unique filename base for THIS specific test run ---
    # Handle None for fname_base_arg from test case 7
    current_test_filename_base = f"{fname_base_arg}_{i}" if fname_base_arg is not None else f"test_case_{i}"
    # Keep the version argument as defined in the test case
    current_test_version = vers_arg

    print(f"Inputs: df=<{type(df_arg).__name__}>, filename_base='{current_test_filename_base}', version='{current_test_version}', subfolder='{subfolder_arg}'")
    try:
        # Pass the UNIQUE filename base and original version arg
        result = up.save_dataframe_to_csv(df_arg, current_test_filename_base, current_test_version, subfolder_arg)
        print(f"✅ Test 4.{i}. → Output Type: {type(result).__name__}, Output Value: {result}")
    except (FileNotFoundError, TypeError, ValueError, AttributeError, OSError, PermissionError) as e:
        print(f"❌ Test 4.{i}. → Expected Error: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"💥 Test 4.{i}. → UNEXPECTED Error: {type(e).__name__}: {e}")
    i += 1

# --- Test Cleanup ---
print("\n--- Test Cleanup ---")

# Ensure project_root was successfully found during setup before cleanup
if isinstance(project_root, Path):
    # 1. Remove the entire temporary test output directory
    #    This cleans files from tests 1, 2, 6, 8, 10(None), 11 etc.
    try:
        if isinstance(temp_test_output_subdir, Path):
            print(f"Removing temporary test output directory: {temp_test_output_subdir}")
            shutil.rmtree(temp_test_output_subdir, ignore_errors=True)
        else:
            print("Skipping temp dir cleanup (path variable not set during setup).")
    except Exception as clean_e1:
        temp_dir_str = str(temp_test_output_subdir) if isinstance(temp_test_output_subdir, Path) else "N/A"
        print(f"Error removing {temp_dir_str}: {type(clean_e1).__name__}: {clean_e1}")

    # 2. Remove the setup file created for test 16
    try:
        if isinstance(file_as_subdir_path, Path):
            print(f"Cleaning up setup file: {file_as_subdir_path}")
            file_as_subdir_path.unlink(missing_ok=True)
        # else: print("Skipping setup file cleanup (path variable not set).")
    except Exception as clean_e2:
        file_path_str = str(file_as_subdir_path) if isinstance(file_as_subdir_path, Path) else "N/A"
        print(f"Error cleaning {file_path_str}: {type(clean_e2).__name__}: {clean_e2}")

    # 3. Clean file potentially created by test 13 in data/project_datasets
    try:
        if isinstance(test13_output_file, Path):
            print(f"Cleaning up file from Test 13: {test13_output_file}")
            test13_output_file.unlink(missing_ok=True)
        # else: print("Skipping Test 13 file cleanup (path variable not set).")
    except Exception as clean_e3:
        file_path_str = str(test13_output_file) if isinstance(test13_output_file, Path) else "N/A"
        print(f"Error cleaning Test 13 file {file_path_str}: {type(clean_e3).__name__}: {clean_e3}")

    # 4. Clean file potentially created by test 14 DIRECTLY in data/
    #    (This step becomes unnecessary IF you modify get_data_folder_path to reject subfolder="")
    try:
        # Reconstruct the unique filename used by test case 14 (index i=14)
        test14_unique_filename_base = f"{TEST_FILENAME_BASE}_14"
        test14_output_file_in_data = data_dir.joinpath(f"{test14_unique_filename_base}_{TEST_VERSION}.csv")
        print(f"Attempting cleanup for file potentially created by Test 14 in data/: {test14_output_file_in_data}")
        test14_output_file_in_data.unlink(missing_ok=True)
    except Exception as clean_e4:
        # Handle potential error during path construction or unlink
        print(f"Error cleaning Test 14 file {str(test14_output_file_in_data) if 'test14_output_file_in_data' in locals() else 'N/A'}: {type(clean_e4).__name__}: {clean_e4}")

else:
    print("Skipping cleanup actions because project_root was not determined during setup.")

print("Cleanup finished.")

# Manual Test Summary:
# --------------------
# ---- Test Setup ---
# Project Root Found: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia
# Cleaning up previous test artifacts if they exist...
# Created temporary test output directory: data/project_datasets/temp_test_outputs_delete_me
# Ensured default data directory exists: data/project_datasets
# Created setup file for Test 16: data/subfolder_is_a_file_setup.txt
# Setup complete.

# --- Running save_dataframe_to_csv tests ---

# --- Test Case 4.1 (Create) ---
# Inputs: df=<DataFrame>, filename='test_output_file', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# DataFrame saved successfully to: data/project_datasets/temp_test_outputs_delete_me/test_output_file_v_test.csv
# ✅ Test 4.1. → Output Type: PosixPath, Output Value: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_v_test.csv

# --- Test Case 4.2 (Skip) ---
# Inputs: df=<DataFrame>, filename='test_output_file', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# File already exists at: data/project_datasets/temp_test_outputs_delete_me/test_output_file_v_test.csv. Skipping save.
# ✅ Test 4.2. → Output Type: NoneType, Output Value: None
# ℹ️  Info Test 4.2: Correctly returned None.

# --- Test Case 4.3 ---
# Inputs: df=<NoneType>, filename_base='test_output_file_3', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# Error saving DataFrame to data/project_datasets/temp_test_outputs_delete_me/test_output_file_3_v_test.csv: 'NoneType' object has no attribute 'to_csv'
# An unexpected error occurred in save_dataframe_to_csv: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_3_v_test.csv: 'NoneType' object has no attribute 'to_csv'
# ❌ Test 4.3. → Expected Error: OSError: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_3_v_test.csv: 'NoneType' object has no attribute 'to_csv'

# --- Test Case 4.4 ---
# Inputs: df=<str>, filename_base='test_output_file_4', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# Error saving DataFrame to data/project_datasets/temp_test_outputs_delete_me/test_output_file_4_v_test.csv: 'str' object has no attribute 'to_csv'
# An unexpected error occurred in save_dataframe_to_csv: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_4_v_test.csv: 'str' object has no attribute 'to_csv'
# ❌ Test 4.4. → Expected Error: OSError: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_4_v_test.csv: 'str' object has no attribute 'to_csv'

# --- Test Case 4.5 ---
# Inputs: df=<int>, filename_base='test_output_file_5', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# Error saving DataFrame to data/project_datasets/temp_test_outputs_delete_me/test_output_file_5_v_test.csv: 'int' object has no attribute 'to_csv'
# An unexpected error occurred in save_dataframe_to_csv: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_5_v_test.csv: 'int' object has no attribute 'to_csv'
# ❌ Test 4.5. → Expected Error: OSError: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_5_v_test.csv: 'int' object has no attribute 'to_csv'

# --- Test Case 4.6 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_6', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# DataFrame saved successfully to: data/project_datasets/temp_test_outputs_delete_me/test_output_file_6_v_test.csv
# ✅ Test 4.6. → Output Type: PosixPath, Output Value: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_6_v_test.csv

# --- Test Case 4.7 ---
# Inputs: df=<DataFrame>, filename_base='test_case_7', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# DataFrame saved successfully to: data/project_datasets/temp_test_outputs_delete_me/test_case_7_v_test.csv
# ✅ Test 4.7. → Output Type: PosixPath, Output Value: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_case_7_v_test.csv

# --- Test Case 4.8 ---
# Inputs: df=<DataFrame>, filename_base='_8', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# DataFrame saved successfully to: data/project_datasets/temp_test_outputs_delete_me/_8_v_test.csv
# ✅ Test 4.8. → Output Type: PosixPath, Output Value: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/_8_v_test.csv

# --- Test Case 4.9 ---
# Inputs: df=<DataFrame>, filename_base='@laj;/-_9', version='v_test', subfolder='project_datasets/temp_test_outputs_delete_me'
# Error saving DataFrame to data/project_datasets/temp_test_outputs_delete_me/@laj;/-_9_v_test.csv: Cannot save file into a non-existent directory: '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/@laj;'
# An unexpected error occurred in save_dataframe_to_csv: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/@laj;/-_9_v_test.csv: Cannot save file into a non-existent directory: '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/@laj;'
# ❌ Test 4.9. → Expected Error: OSError: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/@laj;/-_9_v_test.csv: Cannot save file into a non-existent directory: '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/@laj;'

# --- Test Case 4.10 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_10', version='None', subfolder='project_datasets/temp_test_outputs_delete_me'
# DataFrame saved successfully to: data/project_datasets/temp_test_outputs_delete_me/test_output_file_10_None.csv
# ✅ Test 4.10. → Output Type: PosixPath, Output Value: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_10_None.csv

# --- Test Case 4.11 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_11', version='', subfolder='project_datasets/temp_test_outputs_delete_me'
# DataFrame saved successfully to: data/project_datasets/temp_test_outputs_delete_me/test_output_file_11_.csv
# ✅ Test 4.11. → Output Type: PosixPath, Output Value: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_11_.csv

# --- Test Case 4.12 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_12', version='@laj;/-', subfolder='project_datasets/temp_test_outputs_delete_me'
# Error saving DataFrame to data/project_datasets/temp_test_outputs_delete_me/test_output_file_12_@laj;/-.csv: Cannot save file into a non-existent directory: '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_12_@laj;'
# An unexpected error occurred in save_dataframe_to_csv: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_12_@laj;/-.csv: Cannot save file into a non-existent directory: '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_12_@laj;'
# ❌ Test 4.12. → Expected Error: OSError: Failed to save CSV to /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_12_@laj;/-.csv: Cannot save file into a non-existent directory: '/Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me/test_output_file_12_@laj;'

# --- Test Case 4.13 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_13', version='v_test', subfolder='None'
# DataFrame saved successfully to: data/project_datasets/test_output_file_13_v_test.csv
# ✅ Test 4.13. → Output Type: PosixPath, Output Value: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/test_output_file_13_v_test.csv

# --- Test Case 4.14 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_14', version='v_test', subfolder=''
# An unexpected error occurred in save_dataframe_to_csv: The 'subfolder' argument cannot be an empty string.
# ❌ Test 4.14. → Expected Error: ValueError: The 'subfolder' argument cannot be an empty string.

# --- Test Case 4.15 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_15', version='v_test', subfolder='nonexistent_dir'
# Error: Cannot save file because target directory check failed: Required data directory not found or is not a directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/nonexistent_dir
# ❌ Test 4.15. → Expected Error: FileNotFoundError: Required data directory not found or is not a directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/nonexistent_dir

# --- Test Case 4.16 ---
# Inputs: df=<DataFrame>, filename_base='test_output_file_16', version='v_test', subfolder='subfolder_is_a_file_setup.txt'
# Error: Cannot save file because target directory check failed: Required data directory not found or is not a directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/subfolder_is_a_file_setup.txt
# ❌ Test 4.16. → Expected Error: FileNotFoundError: Required data directory not found or is not a directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/subfolder_is_a_file_setup.txt

# --- Test Cleanup ---
# Removing temporary test output directory: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/temp_test_outputs_delete_me
# Cleaning up setup file: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/subfolder_is_a_file_setup.txt
# Cleaning up file from Test 13: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/project_datasets/test_output_file_v_test.csv
# Attempting cleanup for file potentially created by Test 14 in data/: /Users/reemasipra/Documents/GitHub_Repos/Harry_Potter_Trivia/data/test_output_file_14_v_test.csv
# Cleanup finished.