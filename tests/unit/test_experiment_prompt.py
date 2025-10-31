"""
Unit tests for experiment prompt handling (/scripts/prompts/iterations/run_experiments.py).
"""
from unittest.mock import Mock
import pytest
from scripts.prompts.iterations import run_experiments as exp

class TestExtractMetrics:
    """_summary_

    :return: _description_
    """
    PROMPT_TOKENS = 500
    CONTEXT_TOKENS = 1500
    RESPONSE_TIME = 23.5  # seconds

    ## --Mocked fixtures for different API response scenarios--
    @pytest.fixture
    def mock_api_response(self):
        """
        This simulates a successful API response with complete content.
        The metrics are available in the response object.
        """
        # Initialize a mock response object
        response_prop = Mock()
        # setup the response properties
        response_prop.candidates = [Mock()]
        response_prop.candidates[0].finish_reason.name = "STOP"
        response_prop.prompt_feedback = "block_reason: 0"
        # setup the token counts to get from the usage metadata
        response_prop.usage_metadata = {
            'prompt_token_count': self.PROMPT_TOKENS + self.CONTEXT_TOKENS,
            'candidates_token_count': 2500,
            'total_token_count': 4000
        }

        return response_prop

    @pytest.fixture
    def mock_max_tokens_response(self):
        """
        Simulates a response that was cut off by MAX_TOKENS. This will
        result in a partial response. The API response object will be 
        created with only one candidate with partial content for token counts,
        but the finish reason will be MAX_TOKENS (value 2)
        This also simulates other "bad finish reasons" like RECITATION or OTHER.
        """
        response_prop = Mock()
        response_prop.candidates = [Mock()]
        response_prop.candidates[0].finish_reason.name = "MAX_TOKENS"
        response_prop.prompt_feedback = "block_reason: 0"  # The prompt is fine so will not be blocked

        response_prop.usage_metadata = {
            'prompt_token_count': self.PROMPT_TOKENS + self.CONTEXT_TOKENS,
            'candidates_token_count': 1850,
            'total_token_count': 3850
        }
        return response_prop

    @pytest.fixture
    def mock_prompt_blocked_response(self):
        """
        Simulates a response that was blocked at the prompt stage (e.g., SAFETY, value=3).
        This happens because the model rejects the input prompt even before generating 
        any output. The response object will have no candidates (empty list), the usage 
        metadata will have 0 for output token counts, but the input tokens will still be 
        counted. Most importantly, the prompt feedback will indicate the block reason.
        """
        response_prop = Mock()
        response_prop.candidates = []
        response_prop.prompt_feedback = "block_reason: SAFETY"

        response_prop.usage_metadata = {
            'prompt_token_count': self.PROMPT_TOKENS + self.CONTEXT_TOKENS,
            'candidates_token_count': 0,
            'total_token_count': 2000
        }
        return response_prop

    ## -- Test cases --
    # Happy path: successful API response
    def test_extract_metrics_success(self, mock_api_response):
        """ Happy path: Test extracting metrics from a mock API response."""

        metrics = exp.extract_metrics(mock_api_response, self.RESPONSE_TIME, self.PROMPT_TOKENS)

        assert metrics['finish_reason'] == "STOP"
        assert metrics['prompt_feedback'] == "block_reason: 0"
        assert metrics['response_time_seconds'] == self.RESPONSE_TIME

        assert metrics['tokens']['input_cached'] == 500
        assert metrics['tokens']['input_uncached'] == 1500
        assert metrics['tokens']['output'] == 2500
        assert metrics['tokens']['total'] == 4000

    # Edge case: Incomplete / aborted response from the API
    def test_extract_metrics_incomplete_response(self, mock_max_tokens_response):
        """ 
        Edge case: Test extracting metrics from a mock API response
        that was cut off due to MAX_TOKENS (or OTHER, RECITATION, etc).
        The response will be partial, but we should still be able to
        extract the available metrics.
        """
        metrics = exp.extract_metrics(mock_max_tokens_response, 
                                      self.RESPONSE_TIME, self.PROMPT_TOKENS)

        assert metrics['finish_reason'] == "MAX_TOKENS"
        assert metrics['prompt_feedback'] == "block_reason: 0"
        assert metrics['response_time_seconds'] == self.RESPONSE_TIME

        assert metrics['tokens']['input_cached'] == 500
        assert metrics['tokens']['input_uncached'] == 1500
        assert metrics['tokens']['output'] == 1850
        assert metrics['tokens']['total'] == 3850

    # Edge case: No candidates in the response (prompt blocked)
    def test_extract_metrics_no_candidates(self, mock_prompt_blocked_response):
        """ 
        Edge case: Test extracting metrics from a mock API response
        that has no candidates (empty response).This would happen if the prompt
        was blocked (e.g for SAFETY, MALFORMED_FUNCTION_CALL, etc). 
        The metrics of the failure response are still be extractable and will be logged.
        """
        metrics = exp.extract_metrics(mock_prompt_blocked_response, 0, self.PROMPT_TOKENS)

        assert metrics['finish_reason'] is None
        assert metrics['prompt_feedback'] == "block_reason: SAFETY"
        assert metrics['response_time_seconds'] == 0

        assert metrics['tokens']['input_cached'] == 500
        assert metrics['tokens']['input_uncached'] == 1500
        assert metrics['tokens']['output'] == 0
        assert metrics['tokens']['total'] == 2000

class TestPreparePrompt:
    """
    Unit tests for preparing prompts for experiment runs.
    """
    ## --Mocked fixtures--
    @pytest.fixture
    def mock_file_system(self, tmp_path):
        """
        Creates a complete, temporary file system for the "happy path" test.
        Returns a dictionary of all the components needed for the test.
        """
        # 1. Define all the components
        root = tmp_path
        mock_path = {'project_root': root}

        run_config = {
            'prompt_file': 'prompts/test_prompt.txt',
            'source_text_files': [
                ['chapters/ch1.txt', 'chapters/ch2.txt']
            ],
            'source_info': 'Test Book, Ch 1-2'
        }
        # content for the files
        template_content = "Template: {source_text} | Ref: {book_and_chapter}"
        chapter1_content = "This is chapter 1."
        chapter2_content = "This is chapter 2."

        # 2. Create the fake files
        # create the path by reading from the run_config file
        prompt_path = root / run_config['prompt_file']
        ch1_path = root / run_config['source_text_files'][0][0]
        ch2_path = root / run_config['source_text_files'][0][1]
        # make the necessary directories in tmp_path (e.g. prompts and chapters dir)
        prompt_path.parent.mkdir(parents=True, exist_ok=True)
        ch1_path.parent.mkdir(parents=True, exist_ok=True)
        # write the files to the temp dir using the provided mock content
        prompt_path.write_text(template_content)
        ch1_path.write_text(chapter1_content)
        ch2_path.write_text(chapter2_content)

        # 3. Return everything the tests will need
        return {
            "paths": mock_path,
            "run_config": run_config,
            "template_content": template_content,
            "chapter1_content": chapter1_content,
            "chapter2_content": chapter2_content
        }

    ## -- Test cases --
    # Happy path: successful prompt preparation
    def test_prepare_prompt_assembles_correctly(self, mock_file_system):
        """
        In this test, the prepare_prompt function is expected to read the prompt 
        template from the specified file. Also, read the source text files and 
        combine their content into a single string. Then, format the prompt template
        with the combined chapter text and source info.
        Assumptions:
        - the prompt template file exists and is readable
        - the source text files exist and are readable
        Parameters:
        
        """
        # Arrange
        sample_run_config = mock_file_system['run_config']
        mock_paths = mock_file_system['paths']

        # Act
        final_prompt, template_text = exp.prepare_prompt(sample_run_config, mock_paths)

        # Assert
        assert template_text == mock_file_system['template_content']
        expected_string = (
            f"Template: {mock_file_system['chapter1_content']}\n\n"
            "--- END OF CHAPTER ---\n\n"
            f"{mock_file_system['chapter2_content']} | Ref: {mock_file_system['run_config']['source_info']}"
        )
        assert final_prompt == expected_string

    # Edge case: Missing prompt template file (wrong path)
    def test_prepare_prompt_raises_error_on_missing_prompt_file(self, mock_file_system):
        """
        1. Edge case: Missing prompt template file (wrong path)
        Tests that the function raises FileNotFoundError.
        """
        # Arrange
        data = mock_file_system
        # replace the path with a non-existent file
        data["run_config"]["prompt_file"] = "prompts/non_existent_file.txt"

        # Act and assert
        with pytest.raises(FileNotFoundError):
            exp.prepare_prompt(data["run_config"], data["paths"])

    # Edge case: Prompt template with missing placeholders
    def test_prepare_prompt_raises_error_on_missing_placeholder(self, mock_file_system):
        """
        2. Edge case: Prompt template with missing placeholders
        Tests that the function raises a KeyError from the .format() call.
        """
        data = mock_file_system
        # Overwrite the prompt file to have missing placeholders
        (data["paths"]["project_root"] / data["run_config"]["prompt_file"]).write_text(
            "This template is missing the placeholders."
        )
        with pytest.raises(ValueError, match="missing the required '{source_text}'"):
            exp.prepare_prompt(data["run_config"], data["paths"])

    # Edge case: Missing source text files (e.g. wrong paths)
    def test_prepare_prompt_raises_error_on_missing_source_file(self, mock_file_system):
        """
        3. Edge case: Missing source text files (wrong paths)
        Tests that the function raises FileNotFoundError.
        """
        # 1. ARRANGE
        data = mock_file_system
        # Change the config to point to a chapter file that does NOT exist
        data["run_config"]["source_text_files"] = [["chapters/non_existent_chapter.txt"]]

        # 2. ACT & 3. ASSERT
        with pytest.raises(FileNotFoundError):
            exp.prepare_prompt(data["run_config"], data["paths"])

    # Edge case: Empty source text files
    def test_prepare_prompt_handles_empty_source_files(self, mock_file_system):
        """
        4. Edge case: Empty source text files
        Tests that the function runs successfully but produces an "empty" prompt.
        """
        data = mock_file_system
        # Overwrite the chapter files with empty content
        (data["paths"]["project_root"] / data["run_config"]["source_text_files"][0][0]).write_text("")
        (data["paths"]["project_root"] / data["run_config"]["source_text_files"][0][1]).write_text("")

        with pytest.raises(ValueError, match="Source file is empty"):
            exp.prepare_prompt(data["run_config"], data["paths"])

    # Edge case: Empty prompt template file
    def test_prepare_prompt_raises_error_with_empty_prompt_file(self, mock_file_system):
        """
        5. Edge case: Empty prompt template file
        Tests that the function raises a KeyError (as discovered earlier).
        """
        data = mock_file_system
        # overwrite the mock prompt template to make it empty
        (data["paths"]["project_root"] / data["run_config"]["prompt_file"]).write_text("")

        with pytest.raises(ValueError, match="Prompt template file is empty"):
            exp.prepare_prompt(data["run_config"], data["paths"])
