"""
HP Triiva 
New question generation using Gemini API
Experimentation script automation - integration test
"Edge cases"

Externalities to mock: file integration, api call
Note: This test, its structure, and the mocking strategy
 were developed collaboratively with Gemini 2.5 pro
"""
import yaml
import pytest
from scripts.research.question_generation.iterations import run_experiments as exp

## MOCK Fixtures
    
@pytest.fixture
def mock_environment(mocker, tmp_path):
    """
    Sets up a fully mocked environment (file system and base mocks)
    for our edge case tests to run inside.
    """
    # 1. --- MOCK FILE SYSTEM ---
    mocker.patch(
        'scripts.prompts.iterations.run_experiments.setup_file_paths', 
        return_value={
            'project_root': tmp_path,
            'config': tmp_path / 'config.env',
            'yaml': tmp_path / 'experiment.yaml',
            'output_dir': tmp_path / 'llm_outputs'
            })
    
    # 2. --- MOCK BASE HELPERS ---
    # fetching the api key
    mocker.patch(
        'scripts.prompts.iterations.run_experiments.configure_api', 
        return_value=None)
    # calculating the prompt token count
    mocker.patch(
        'scripts.prompts.iterations.run_experiments.get_prompt_template_token_count',
        return_value=100)

    # 3. --- CREATE FAKE FILES ---
    # output dir and file
    (tmp_path / 'llm_outputs').mkdir()
    # api key mock
    (tmp_path / 'config.env').write_text("GEMINI_API_KEY=fake_key")
    # Define paths for test functions to use
    prompt_path = tmp_path / 'prompt_template.txt'
    source_path = tmp_path / 'source_chapter_1.txt'
    
    # prompt template with placeholders
    (tmp_path / 'prompt_template.txt').write_text(
        "Prompt: {source_text} | Ref: {book_and_chapter}")
    # source text file 
    (tmp_path / 'source_chapter_1.txt').write_text("This is the source text.")

    # 4. --- CREATE FAKE YAML ---
    # fake run content for the yaml file
    test_yaml_content = {
        'experiments': [
            {
                'id': 'edge_case_exp',
                'model': 'gemini-pro',
                'common_parameters': {'temperature': 0.5},
                'runs': [
                    {
                        'version': 'run_v1_fails',
                        'status': 'pending', 
                        'prompt_file': 'prompt_template.txt',
                        'source_info': 'Book 1, Ch 1',
                        'source_text_files': [['source_chapter_1.txt']],
                        'model_parameters': {'candidate_count': 1}
                    }
                ]
            }
        ]
    }
    # fake yaml file with content
    yaml_path = tmp_path / 'experiment.yaml'
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(test_yaml_content, f)
        
    # 5. --- RETURN THE PATHS that are needed by the orchestrator ---
    # The test function will need this to read the final YAML
    return {
        'yaml_path': yaml_path,
        'output_dir': tmp_path / 'llm_outputs',
        'prompt_path': prompt_path,
        'source_path': source_path
        }

## EDGE case tests

#--- TEST 1: API call fails---

def test_main_handles_api_failure(mocker, mock_environment):  # pylint: disable=redefined-outer-name
    """Tests that if make_api_call() raises an Exception, the main
    orchestrator catches it and logs the run as 'failed'.
    """

    # 1. --- ARRANGE: Setup the failure ---

    # This is the key part of this test:
    # mock 'make_api_call' to raise an Exception when called.
    mocker.patch(
        'scripts.prompts.iterations.run_experiments.make_api_call',
        side_effect=Exception("Simulated 500 API Error"))

    # Get the yaml_path from our setup fixture
    yaml_path = mock_environment['yaml_path']

    # 2. --- ACT: Run the script---
    exp.main() # This should NOT crash

    # 3. --- ASSERT the results ---

    # Read the YAML file back in
    with open(yaml_path, 'r', encoding='utf-8') as f:
        updated_config = yaml.safe_load(f)

    run1 = updated_config['experiments'][0]['runs'][0]

    # --- Assert the failure was logged correctly ---
    assert run1['status'] == 'failed'
    assert 'metrics' not in run1 # Metrics should not be logged on failure
    assert 'output_files' not in run1 # No files should be saved

    # Assert the error message was logged to 'notes'
    assert 'notes' in run1
    assert "Simulated 500 API Error" in run1['notes']

    # Assert the status history was updated
    assert 'status_history' in run1
    assert run1['status_history'][-1]['status'] == 'failed'

    print("\nTest passed! 'main' correctly handled the API failure.")

# failure of a helper method
def test_main_handles_helper_failure(mocker, mock_environment):  # pylint: disable=redefined-outer-name
    """
    Tests that if a helper other than the API call fails
    (e.g., prepare_prompt), the main 'except' block still
    catches it and logs the run as 'failed'.
    """
    # 1. --- ARRANGE: setup the failure ---

    # mock 'prepare_prompt' to raise an error
    mocker.patch(
        'scripts.prompts.iterations.run_experiments.prepare_prompt',
        side_effect=ValueError("Simulated prompt prep error")
    )

    # DON'T need to mock 'make_api_call' because the
    # script will fail before it even gets there.

    # Get the yaml_path from our setup fixture
    yaml_path = mock_environment['yaml_path']

    # 2. --- ACT: Run the script ---
    exp.main() # This should also NOT crash

    # 3. --- ASSERT: the results ---

    # Read the YAML file back in
    with open(yaml_path, 'r', encoding='utf-8') as f:
        updated_config = yaml.safe_load(f)

    run1 = updated_config['experiments'][0]['runs'][0]

    # --- Assert the failure was logged correctly ---
    assert run1['status'] == 'failed'
    assert 'notes' in run1
    # Check that the *correct* error message was logged
    assert "Simulated prompt prep error" in run1['notes']
    assert 'status_history' in run1
    assert run1['status_history'][-1]['status'] == 'failed'

    print("\nTest passed! 'main' correctly handled a helper function failure.")

# no placeholders in prepare_prompt - make sure the orchestrator can handle it    
def test_main_handles_missing_placeholder(mock_environment):  # pylint: disable=redefined-outer-name
    """
    Tests that if the prompt template is missing a required placeholder,
    the 'prepare_prompt' helper raises a ValueError and 'main' catches it
    correctly.
    """
    # 1. --- ARRANGE: setup the failure ---

    # Get paths from the fixture
    yaml_path = mock_environment['yaml_path']
    prompt_path = mock_environment['prompt_path']

    # *Overwrite* the prompt fixture to not have any placeholders
    prompt_path.write_text("This prompt is missing the placeholders.")

    # 2. --- ACT: run the script ---
    exp.main() # This should NOT crash

    # 3. --- ASSERT: the results ---

    with open(yaml_path, 'r', encoding='utf-8') as f:
        updated_config = yaml.safe_load(f)

    run1 = updated_config['experiments'][0]['runs'][0]

    assert run1['status'] == 'failed'
    assert 'notes' in run1
    # Check that the *specific* error from your helper was logged
    assert "missing the required '{source_text}' placeholder" in run1['notes']
    assert 'status_history' in run1
    assert run1['status_history'][-1]['status'] == 'failed'

    print("\nTest passed! 'main' correctly handled missing placeholder.")

# empty prompt file - make sure the orchestrator can handle it 
def test_main_handles_empty_source_file(mock_environment):  # pylint: disable=redefined-outer-name
    """
    Tests that if a source text file is empty, the'prepare_prompt'
    helper raises a ValueErrorand 'main' catches it correctly.
    """
    # 1. --- ARRANGE: setup the failure ---

    # Get paths from the fixture
    yaml_path = mock_environment['yaml_path']
    source_path = mock_environment['source_path']

    # *Overwrite* the prompt_template fixture with an "empty" one
    source_path.write_text("   ") # Just whitespace

    # 2. --- ACT ---
    exp.main() # This should NOT crash

    # 3. --- ASSERT---

    with open(yaml_path, 'r', encoding='utf-8') as f:
        updated_config = yaml.safe_load(f)

    run1 = updated_config['experiments'][0]['runs'][0]

    assert run1['status'] == 'failed'
    assert 'notes' in run1
    # Check that the *specific* error from your helper was logged
    assert "Source file is empty" in run1['notes']
    assert 'status_history' in run1
    assert run1['status_history'][-1]['status'] == 'failed'

    print("\nTest passed! 'main' correctly handled empty source file.")
