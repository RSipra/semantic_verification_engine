"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

Utility functions for navigating and managing project file paths.

This module was developed for the HP trivia game but with the clear design
intent for it to be able to be a standalone module for future projects.
It centralizes common path operations, such as finding project roots
(via `.git`), locating specific files recursively, and accessing standard
data subdirectories.

Assumptions for Reusability:
----------------------------
For these functions to work correctly across different projects, the projects
are assumed to follow a specific structure:

1.  **Git Repository:** The project root must contain a '.git' directory, as
    `find_project_root` relies on this for identification.
2.  **Top-Level 'data/' Directory:** Functions like `get_data_folder_path` and
    `save_dataframe_to_csv` expect a main 'data/' directory to exist directly
    under the project root. They construct paths relative to this folder
    (e.g., 'project_root/data/your_subfolder').
3.  **Default Subfolder:** The default behavior for functions specifying a
    'subfolder' often assumes a 'project_datasets' directory exists within
    'data/' (i.e., 'project_root/data/project_datasets/').

Adhering to these conventions allows this module to be easily reused.
"""
import os
from pathlib import Path
from typing import Optional, List
# import warnings
import pandas as pd


def find_project_root(start_path: Optional[str] = None) -> Path:
    """
    Find the project root directory by looking for a `.git` folder starting
    from the given path (provided as a string) and moving upward.

    Args:
        start_path (str, optional): The starting path string (representing a file or directory)
            for the search. If None, defaults to the directory of the file calling this
            function, or the current working directory as a fallback.

    Raises:
        FileNotFoundError: If no `.git` directory is found in the parent paths,
                           or if the provided start_path string doesn't resolve
                           to an existing file or directory.
        ValueError: If there's an issue processing the start_path string.


    Returns:
        Path: Absolute path to the project root directory.
    """
    effective_start_path: Path

    if start_path is None:
        # Determine the default starting point if no path string is provided
        try:
            # Prefer the directory containing the current file (__file__)
            anchor_file = Path(__file__).resolve()
            effective_start_path = anchor_file.parent
        except NameError:
            # Fallback to current working directory if __file__ is not available
            effective_start_path = Path(os.getcwd()).resolve()
        #print(f"Debug: No start_path provided, using default: {effective_start_path}") #Opt debug

    else:
        # start_path is guaranteed to be a string here (based on type hint)
        try:
            # Convert the input string to a Path object and resolve it to an absolute path.
            # Using strict=True to ensure the path exists, raising FileNotFoundError otherwise.
            effective_start_path = Path(start_path).resolve(strict=True)
            # print(f"Debug: Provided start_path='{start_path}', resolved to: {effective_start_path}") # Optional debug
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"The provided start_path string '{start_path}' does not correspond to an existing file or directory."
            ) from e
        except Exception as e:
            # Catch other potential errors during Path creation/resolution
            raise ValueError(f"Error processing start_path string '{start_path}': {e}") from e

    # Now effective_start_path is guaranteed to be an existing, absolute Path object

    # Determine the directory to start the upward search from
    if effective_start_path.is_file():
        current_path = effective_start_path.parent
    elif effective_start_path.is_dir():
        current_path = effective_start_path
    else:
        # This condition should theoretically not be reached due to resolve(strict=True)
        # and the is_file/is_dir checks, but added for completeness.
        raise ValueError(f"Resolved path '{effective_start_path}' is neither a file nor a directory.")

    # Loop through the determined starting directory and its parents
    # print(f"Debug: Starting search from directory: {current_path}") # Optional debug
    for parent in [current_path, *current_path.parents]:
        # print(f"Debug: Checking parent: {parent}") # Optional debug
        git_dir = parent / ".git"
        if git_dir.exists() and git_dir.is_dir():
            # print(f"Debug: Found .git in: {parent}") # Optional debug
            # Return the absolute path of the directory containing .git
            # .resolve() here ensures absolute path, though `parent` should already be absolute.
            return parent.resolve()

    # If the loop completes without finding a .git directory
    raise FileNotFoundError(f"No .git directory found in the parent directories of {effective_start_path}")

# --- Updated get_data_folder_path function ---
# Note: Type hint changed to Optional[str] to reflect explicit None is possible input
def get_data_folder_path(subfolder: Optional[str] = "project_datasets") -> Path:
    """
    Gets the absolute path to an EXISTING data subfolder relative to the project root.

    Verifies the target subfolder exists within the project's 'data/'
    directory and raises errors if not found, not a directory, or if input
    arguments are invalid. Does NOT create directories.

    Args:
        subfolder (str, optional): The name of the subfolder within the main 'data/'
            directory. Defaults to "project_datasets". If explicitly passed as
            None, the default value ("project_datasets") will be used. Cannot be
            an empty string.

    Returns:
        Path: The absolute path to the requested, existing data subfolder.

    Raises:
        ValueError: If the 'subfolder' argument is an empty string.
        FileNotFoundError: If the project root (.git) cannot be found by the
                           find_project_root function call.
        FileNotFoundError: If the target data subfolder (data/<subfolder>)
                           does not exist or is not a directory.
    """
    
    # --- Input Handling and Validation ---
    effective_subfolder: str
    if subfolder is None:
        # a. Handle explicit None input by using the default value.
        effective_subfolder = "project_datasets"
    else:
        # If not None, it should be a string (per type hint)
        effective_subfolder = subfolder

    # b. Check for empty string AFTER handling None.
    if not effective_subfolder:  # This catches empty string ""
        raise ValueError("The 'subfolder' argument cannot be an empty string.")

    
    # 1. Find the project root (start search from this file's location or CWD)
    try:
        project_root = find_project_root()
    except FileNotFoundError as e:
        raise FileNotFoundError(
            "Project root (.git directory) could not be found."
        ) from e 

    # 2. Construct the full path to the target subfolder
    target_path = project_root.joinpath("data").joinpath(effective_subfolder)

    # 3. Check if the directory exists AND is a directory. Do NOT create.
    if not target_path.is_dir():
        raise FileNotFoundError(
            f"Required data directory not found or is not a directory: {target_path}"
        )

    # 4. Return the absolute path to the existing subfolder
    return target_path

def save_dataframe_to_csv(df: pd.DataFrame,
                          filename_base: str, 
                          version: str, 
                          subfolder: str = "project_datasets") -> Optional[Path]:
    """
    Saves a DataFrame to a CSV file within a specified data subfolder
    relative to the project root, including versioning in the filename.

    Checks if the target directory exists and raises FileNotFoundError if not.
    If the target *file* already exists, it prints a message, skips saving,
    and returns None. Otherwise, it saves the file and returns its Path.

    Args:
        df (pd.DataFrame): The pandas DataFrame to save.
        filename_base (str): The base name for the file (e.g., 'processed_data').
        version (str): The version string (e.g., 'v0', 'v1', 'final').
        subfolder (str): The subfolder within the project's 'data' directory
                         where the file should be saved. Defaults to 'project_datasets'.

    Returns:
        Optional[Path]: The absolute `Path` object if the CSV was saved successfully,
                       or `None` if the file already existed and was skipped.

    Raises:
        FileNotFoundError: If the target directory specified by `subfolder`
                           (via get_data_folder_path) does not exist.
        OSError: If an OS-level error occurs during saving (e.g., permissions,
                 disk full), often wrapping exceptions from df.to_csv.
        Exception: Other potential exceptions from pandas df.to_csv.
    """
    try:
        # 1. Get and validate target directory path (will raise FileNotFoundError if dir doesn't exist)
        target_dir = get_data_folder_path(subfolder)

        # 2. Construct filename and full save path
        save_filename = f"{filename_base}_{version}.csv"
        save_path = target_dir / save_filename

        # 3. Try to get relative path for pretty printing :)
        try:
            project_root = find_project_root()
            relative_path_str = str(save_path.relative_to(project_root))
        except (ValueError, FileNotFoundError):
            relative_path_str = str(save_path) # Fallback to absolute path string

        # 4. Check if the specific *file* already exists
        if not save_path.exists():
            # 5. Attempt to save if file doesn't exist
            try:
                df.to_csv(save_path, index=False)
                print(f"DataFrame saved successfully to: {relative_path_str}")
                return save_path # Return Path object on success
            except Exception as e:
                # Catch potential errors from to_csv itself
                print(f"Error saving DataFrame to {relative_path_str}: {e}")
                # Re-raise potentially wrapped in OSError or just re-raise
                # Consider more specific exception handling if needed
                raise OSError(f"Failed to save CSV to {save_path}: {e}") from e
        else:
            # 6. File already exists - print message and return None
            message = f"File already exists at: {relative_path_str}. Skipping save."
            print(message)
            return None # Return None to indicate skipped operation

    except FileNotFoundError as e:
         # Catch error if target_dir doesn't exist (from get_data_folder_path)
        print(f"Error: Cannot save file because target directory check failed: {e}")
        raise e # Re-raise the FileNotFoundError
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred in save_dataframe_to_csv: {e}")
        raise e

def find_file_path(filename: str, source_directory: Optional[str] = None) -> Path:    
    """Finds a file by searching recursively within a specified directory or project root.

        Searches recursively starting from a given root directory for a file
        matching the provided filename. If no search root directory path is
        specified via `search_root_path_str`, the search defaults to starting
        from the project's root directory (identified by the '.git' folder).

        This function ensures exactly one matching file is found within the search
        scope to avoid ambiguity.

        Args:
            filename (str): The exact name of the file to search for
                (e.g., 'config.yaml', 'main_script.py'). Globs/wildcards might work
                depending on underlying `rglob` behavior but are primarily intended
                for exact filenames.
            source_directory (str, optional): A string representing the path
                to the directory where the recursive search should begin.
                Can be relative (e.g., 'data/images') or absolute. If None,
                the search starts from the project root determined by
                `find_project_root()`. Defaults to None.

        Returns:
            Path: The absolute `pathlib.Path` object to the uniquely found file.

        Raises:
            FileNotFoundError: If the default project root cannot be determined when
                `search_root_path_str` is None (e.g., .git not found).
            FileNotFoundError: If the path provided in `search_root_path_str`
                does not resolve to an existing directory.
            ValueError: If the `search_root_path_str` is invalid (e.g., cannot be
                parsed as a path due to invalid characters).
            FileNotFoundError: If no file matching `filename` is found recursively
                under the determined search root.
            FileNotFoundError: If multiple files matching `filename` are found
                recursively under the search root (ambiguity).
            OSError: If a filesystem-related error occurs during the search,
                other than lack of permissions.
            PermissionError: If file system permissions prevent searching within
                or under the search root directory.
        """

    search_root: Path  # This will hold the verified Path object for the search base
    
    # --- Step 0: Enforce input as strings strictly, raise TypeError if not  ---
    if not isinstance(filename, str):
        raise TypeError(f"Argument 'filename' must be a string, not {type(filename).__name__}.")
    # Check 'file_folder' only if it's provided (i.e., not None)
    if source_directory is not None and not isinstance(source_directory, str):
        raise TypeError(f"Argument 'source_directory' must be a string or None, not {type(source_directory).__name__}.")
    
    # --- Step 1: Determine the Search Root Directory ---
    if source_directory is None:
        # --- Default Case: No search root path provided ---
        try:
            # Find the project root to use as the default search root
            search_root = find_project_root()
            # print(f"Debug: No search root provided. Using project root: {search_root}")
        except FileNotFoundError as e:
            # If find_project_root fails, cannot proceed
            raise FileNotFoundError(
                "Cannot search: Default project root could not be determined."
            ) from e
    else:
        # --- User Provided Case: A path string for the search root ---
        try:
            # Convert the input string to a Path object
            potential_root = Path(source_directory)
            # Resolve the path to make it absolute (handles relative paths like ".")
            search_root = potential_root.resolve()

            # IMPORTANT: Check if the resolved path is actually an existing directory
            if not search_root.is_dir():
                raise FileNotFoundError(
                    f"Provided search root path is not an existing directory: {search_root}"
                )
            # print(f"Debug: Using provided search root: {search_root}")
        except FileNotFoundError as e:
             # Re-raise the specific error from the is_dir check
            raise e
        except Exception as e:
            # Catch other potential errors during Path() creation or .resolve()
            raise ValueError(
                f"Invalid or problematic search root path string provided '{source_directory}': {e}"
            ) from e

    # --- Step 2: Perform the Recursive File Search ---
    # print(f"Debug: Recursively searching for '{filename}' under '{search_root}'")
    try:
        # Use rglob for recursive search. Convert generator to list immediately.
        found_files: List[Path] = list(search_root.rglob(filename))
    except PermissionError as e:
        raise PermissionError(f"Permission denied while searching for '{filename}' under '{search_root}'.") from e
    except Exception as e:
        # Catch other potential filesystem errors during the search
        raise OSError(f"Error during file search for '{filename}' under '{search_root}': {e}") from e

    # --- Step 3: Analyze Search Results ---
    if len(found_files) == 0:
        # Case: No files found
        raise FileNotFoundError(f"File '{filename}' not found recursively under '{search_root}'.")

    if len(found_files) > 1:
        # Case: Multiple files found - raise error to avoid ambiguity
        # Create a formatted list of relative paths for the error message
        relative_paths_str = "\n".join([f"- {p.relative_to(search_root)}" for p in found_files])
        raise FileNotFoundError(
            f"Ambiguity: Multiple files named '{filename}' found under '{search_root}':\n{relative_paths_str}"
        )

    # --- Step 4: Return Result ---
    # Case: Exactly one file found
    # The path from rglob starting from a resolved path should already be absolute.
    return found_files[0]
