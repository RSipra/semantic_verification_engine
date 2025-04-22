# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) principles where applicable during development.

**Versioning Strategy (Pre-1.0.0):** Versions in the `0.x.0` range correspond to the completion of the main development phases outlined in the project workflow documentation.

**Note:** Formal changelog tracking began on April 19, 2025. Project history prior to this date exists in the Git commit log...

## [Unreleased]

### Added
- *(Nothing yet)*

### Changed
- *(Nothing yet)*

### Deprecated
- *(Nothing yet)*

### Removed
- *(Nothing yet)*

### Fixed
- *(Nothing yet)*

### Security
- *(Nothing yet)*

## [0.1.0] - 2025-04-22
### Added
- `find_project_root` (utils.utils_paths): Fallback to using Current Working Directory (CWD) when `__file__` is unavailable (improves notebook/REPL use).
- `find_file_path` (utils.utils_paths): Strict input type validation (`TypeError` for non-string `filename` or `file_folder`).
- `find_file_path` (utils.utils_paths): Validation for provided `file_folder` path string (must resolve to an existing directory).
- `find_file_path` (utils.utils_paths): Robust error handling for file search results (raises `FileNotFoundError` for 0 or >1 matches, lists duplicates).
- `find_file_path` (utils.utils_paths): Specific error handling for `PermissionError` and `OSError` during filesystem search.
- `save_dataframe_to_csv` (utils.utils_paths): Display user-friendly relative paths (from project root, where possible) in status messages.

### Changed
- `find_project_root` (utils.utils_paths): Improved robustness for handling various `start_path` inputs (str/Path, relative/absolute, file/dir). Improved error context using `raise ... from ...`.
- `get_data_folder_path` (utils.utils_paths): **Behavior Change:** Now *checks* if the target data subfolder exists (for read-only use cases) and raises `FileNotFoundError` if absent, instead of creating it. *(Note: Requires further fixes to handle explicit `None` and reject `""` inputs for `subfolder`)*.
- `find_file_path` (utils.utils_paths): Complete rewrite for clarity, robustness, and correct search scoping using `rglob` for recursive search.
- `find_file_path` (utils.utils_paths): Optional `file_folder` parameter updated to explicitly expect a string; internal logic handles path conversion/validation.
- `save_dataframe_to_csv` (utils.utils_paths): Refactored function for clarity and improved internal error handling around save operation.
- `save_dataframe_to_csv` (utils.utils_paths): Updated return type to `Optional[Path]` (`Path` on success, `None` if file exists/skipped).

### Removed
- `find_project_root_in_notebook`: Made redundant by CWD fallback added to `find_project_root`.

### Fixed
- `find_project_root` (utils.utils_paths): Ensured `.git` check verifies it's a directory.
- `get_data_folder_path` (utils.utils_paths): Corrected logic to reliably find project root *before* constructing the data path.
- `find_file_path` (utils.utils_paths): Corrected search scope to strictly search *only* under the determined root directory, preventing potential system-wide searches identified during testing.
- `save_dataframe_to_csv` (utils.utils_paths): Removed redundant internal check for target directory existence (now correctly handled by `get_data_folder_path`).

### Fixed
* **Utils Module:** - `find_project_root`: Corrected handling of relative `Path` or `str` inputs to prevent incorrect root directory detection (previously returned "." in some cases).
  - `find_project_root`: Ensured the check for `.git` verifies it is a directory, not just any file/artifact.
  ### Changed
* **Utils Module:** - `find_project_root`: Added fallback to use the Current Working Directory (CWD) when the `__file__` attribute is not defined. This improves usability in non-script environments like notebooks or interactive REPLs.
- `find_data_path`: based on testing added error checking to make sure directory exists before providing path.
  ### Removed
* **Utils Module:** - `find_project_root_in_notebook`: Removed this function as its specific use case is now covered by the improvements to the main `find_project_root` function (CWD fallback).

