"""
==================================================================
HARRY POTTER TRIVIA GAME 
==================================================================

Utils - provides centralized helper functions for the notebooks

The helper functions are for paths etc
------------------------------------------------------------------
"""

from pathlib import Path
from typing import Optional, Union
import warnings
import pandas as pd

# Optional[Path] = None is equivalent to Union(Path, None)
def find_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Find the project root directory by looking for a `.git` folder starting 
    from the given path and moving upward. This is primarily used in scripts 
    and modules where `__file__` is available.

    Args:
        current_path (Path, optional): The starting path for the search.
            Defaults to the path of the current file.

    Raises:
        FileNotFoundError: If no `.git` directory is found in the current or parent paths.

    Returns:
        Path: Absolute path to the project root directory.
    """
    # in case a file path is not provided, the function uses the path of the cwd
  
    if start_path is None:
        start_path = Path(__file__).resolve()
    
    # initialize the current_path to begin at start_path
    current_path = start_path
    
    # loops through parent folders until it finds the .git file to id root dir /else returns error    
    for parent in [current_path, *current_path.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError("No .git directory found in any parent folders.")


def get_project_root_from_notebook() -> Path:
    """
    Notebook-friendly wrapper to find the project root.

    This function is intended for use in Jupyter or Colab notebooks where __file__ is not available.
    It attempts to find the project root by starting from the current working directory and walking 
    up the parent directories to locate a .git folder (used to identify the project root).

    ⚠️ Note for Google Colab:
    - In Colab, ensure the repository is cloned and the working directory is changed to the repo root.
    - If the .git folder is not found (e.g., when uploading only individual files), the function will 
      fall back to returning the current working directory with a warning.

    :return: Path object pointing to the project root, or current working directory as fallback.
    """
    try:
        return find_project_root(start_path=Path.cwd())
    except FileNotFoundError:
        message = (
            "⚠️ Could not find project root (.git folder) from the current "
            "working directory. Falling back to Path.cwd(). Ensure you are "
            "running this from within the project structure, or that the "
            "project uses Git."
        )
        warnings.warn(message)
        return Path.cwd().resolve() 

def find_file_path(filename: str, search_root: Optional[Path] = None) -> Path:    
    """
    Finds the absolute path of a file by searching recursively under a given root.

    By default, it searches from the project root determined from the notebook context.
    Raises an error if the file is not found or if multiple files with the
    same name are found. # MODIFIED: Docstring reflects multi-file error

    Args:
        filename (str): The name of the file to search for (e.g., 'my_data.csv').
        search_root (Path | None, optional): The directory to start the search from. # MODIFIED: Type hint and optional
            If None, defaults to the project root found via
            `get_project_root_from_notebook()`. Defaults to None.

    Returns:
        Path: The absolute path to the found file.

    Raises:
        FileNotFoundError: If the file is not found, or if multiple files
                           with the same name exist under the `search_root`.
    """
    
    # In case search_root is not provided, it finds the root folder with function
    if search_root is None:
        search_root = get_project_root_from_notebook()

    # Input validation for search_root
    if not isinstance(search_root, Path):
        raise TypeError("search_root must be a Path object or None.")
    if not search_root.is_dir():
        raise FileNotFoundError(f"Search root directory does not exist: {search_root}")

    # Collect all paths found using rglob (rglob recursively searches for filename starting from
    # project root and then subdirectores for a match).
    # This is incase there are multiple files
    found_paths = list(search_root.rglob(filename))

    # if no path found, return error
    if not found_paths:
        raise FileNotFoundError(f"File '{filename}' not found under {search_root}")

    # Check for multiple files found, raise error, and provide relative paths to locate duplicates
    if len(found_paths) > 1:
        relative_paths = [p.relative_to(search_root) for p in found_paths]
        raise FileNotFoundError(
            f"Multiple files named '{filename}' found under {search_root}:\n"
            f"{[str(rp) for rp in relative_paths]}" # Show relative paths of duplicates
        )

    # Return the resolved path of the single file found
    return found_paths[0].resolve()

def get_data_folder_path(subfolder: str = "project_datasets") -> Path:
    """
    Gets the absolute path to a specific subfolder within the 'data' directory,
    relative to the project root found from the notebook's perspective.

    Ensures the target directory exists, creating it if necessary.

    Args:
        subfolder (str): The name of the subfolder within the main 'data'
                         directory. Defaults to 'project_datasets'.

    Returns:
        Path: The absolute path to the requested data subfolder.
    """
    project_root = get_project_root_from_notebook()
    data_path = project_root / "data" / subfolder

    return data_path

def save_dataframe_to_csv(df: pd.DataFrame,
                          filename_base: str, 
                          version: str, 
                          subfolder: str = "project_datasets") -> Union[Path,str]:
    """
    Saves a DataFrame to a CSV file within a specified data subfolder
    relative to the project root. Includes versioning in the filename.

    *** IMPORTANT ***
    This function REQUIRES the target directory (e.g., 'data/project_datasets')
    to exist manually before calling it. It will raise an error if the
    directory is not found. It does not create directories.

    If the file already exists, it prints a message and does not overwrite.

    Args:
        df (pd.DataFrame): The pandas DataFrame to save.
        filename_base (str): The base name for the file (e.g., 'processed_data').
        version (str): The version string (e.g., 'v0', 'v1', 'final').
        subfolder (str): The subfolder within the project's 'data' directory.
                         Defaults to 'project_datasets'.

    Returns:
        Path | str: The absolute `Path` object where the CSV was saved,
                   or an informative string message if the file already exists.

    Raises:
        FileNotFoundError: If the target directory specified by `subfolder`
                           does not exist.
        # Other exceptions possible from df.to_csv for other file issues.
    """

    target_dir = get_data_folder_path(subfolder)
    save_filename = f"{filename_base}_{version}.csv"
    full_path = target_dir / save_filename

    try:
        project_root = get_project_root_from_notebook()
        relative_path = full_path.relative_to(project_root)
    except ValueError:
        relative_path = full_path # Fallback

    if not full_path.exists():
        # Explicit check for parent directory existence
        if not full_path.parent.is_dir():
            raise FileNotFoundError(
                f"Target directory does not exist: '{full_path.parent}'. "
                f"Please create it manually before saving."
            )

        try:
            # Attempt to save, knowing the directory check passed
            df.to_csv(full_path, index=False)
            print(f"DataFrame saved successfully to: {relative_path}")
            return full_path
        except Exception as e:
            # Catch potential errors from to_csv itself (permissions, disk space, etc.)
            print(f"Error during df.to_csv to {relative_path}: {e}")
            raise
    else:
        message = f"File already exists at: {relative_path}. Skipping save."
        print(message)
        return message
