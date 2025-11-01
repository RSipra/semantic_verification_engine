"""
HP Triiva 
New question generation using Gemini API
Experimentation script automation - integration test
"Happy case - successful api call"

Externalities to mock: file integration, api call
Note: This test, its structure, and the mocking strategy
 were developed collaboratively with Gemini 2.5 pro
"""
import yaml
from scripts.prompts.iterations import run_experiments as exp

def test_main_orchestrator(mocker, tmp_path):
    """
    Tests the main() orchestrator's ability to read config,
    prepare data, call the (mocked) API, and log results.
    """
    
## 1. -- Arrange: SETUP MOCKS ----

## file integration
# The mocker will replace the dict in `setup_file_paths` to tmp_path
    mocker.patch('scripts.prompts.iterations.run_experiments.setup_file_paths', return_value={
            'project_root' : tmp_path, 
            'config' :  tmp_path / 'config.env',
            'yaml' : tmp_path / 'experiment.yaml',
            'output_dir': tmp_path / 'llm_outputs'
    })
    # setup the fake subdirs in tmp_path for the orchestrator
    (tmp_path / 'llm_outputs').mkdir()  
    # create fake files: prompt template with placeholders, source texts
    (tmp_path / 'prompt_template.txt').write_text(
    "Prompt: {source_text} | Ref: {book_and_chapter}"
    )
    (tmp_path / 'source_chapter_1.txt').write_text("This is the source text for chapter 1.")
    (tmp_path / 'source_chapter_2.txt').write_text("This is the source text for chapter 2.")
    
    # fake yaml experiment runs and then write it to file
    test_yaml_content = {
        'experiments': [
            {
                'id': 'test_exp_001',
                'model': 'gemini-pro',
                'common_parameters': {'temperature': 0.5},
                'runs': [
                    {
                        'version': 'run_v1_pending',
                        'status': 'pending', # This should run
                        'prompt_file': 'prompt_template.txt',
                        'source_info': 'Book 1, Ch 1',
                        'source_text_files': [
                            ['source_chapter_1.txt','source_chapter_2.txt']
                        ],
                        'model_parameters': {'candidate_count': 1}
                    },
                    {
                        'version': 'run_v2_completed',
                        'status': 'completed', # This should be skipped
                        'prompt_file': 'prompt_template.txt',
                        'source_text_files': [
                            ['source_chapter_1.txt','source_chapter_2.txt']
                        ]
                    }
                ]
            }
        ]
    }
    yaml_path = tmp_path / 'experiment.yaml'
    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(test_yaml_content, f)

## Mock API call
    
    # create the fake response objects that the helper methods (extract_metrics, save_response_to_files) expect
    class MockContent:
        def __init__(self, text):
            self.parts = [MockPart(text)]
            
    class MockPart:
        def __init__(self, text):
            self.text = text
            
    class MockCandidate:
        def __init__(self, text, finish_reason):
            self.content = MockContent(text)
            self.finish_reason = MockFinishReason(finish_reason)
            
    class MockFinishReason:
        def __init__(self, name):
            self.name = name
            
    # This class is the key! We are no longer using a dict.
    class MockUsage:
        def __init__(self, prompt, candidates, total):
            self.prompt_token_count = prompt
            self.candidates_token_count = candidates
            self.total_token_count = total
            
    class MockResponse:
        def __init__(self, text, finish_reason="STOP"):
            self.candidates = [MockCandidate(text, finish_reason)]
            # We now assign the MockUsage *object* here
            self.usage_metadata = MockUsage(500, 150, 650) # Fake token counts
            self.prompt_feedback = "N/A"
    
    mock_api_response = MockResponse(
        text='{"summary": "This is the mock API response"}'
    )
    
    
    # fake api key extraction - mimic method, return nothing
    mocker.patch('scripts.prompts.iterations.run_experiments.configure_api', return_value=None)
    
    # mock the main api call:
    mocker.patch('scripts.prompts.iterations.run_experiments.make_api_call',
                 return_value= (mock_api_response, 1.23) )  #(response obj, response time)
    
    # mock the token count method
    mocker.patch('scripts.prompts.iterations.run_experiments.get_prompt_template_token_count',
                 return_value=100)

##  2. --- Act: RUN THE SCRIPT ---
    exp.main()
    
## 3. --- ASSERT THE RESULTS ---
# Read the YAML file *back in* to see if it was changed
    with open(yaml_path, 'r', encoding='utf-8') as f:
        updated_config = yaml.safe_load(f)

    # Check the 'pending' run
    run1 = updated_config['experiments'][0]['runs'][0]
    assert run1['version'] == 'run_v1_pending'
    assert run1['status'] == 'completed' # Was it updated?
    assert run1['metrics']['response_time_seconds'] == 1.23
    assert run1['metrics']['tokens']['input_cached'] == 100
    assert run1['metrics']['tokens']['input_uncached'] == 400 # 500 (api_total) - 100 (cached)
    assert run1['metrics']['tokens']['output'] == 150
    assert 'status_history' in run1
    assert run1['status_history'][-1]['status'] == 'completed'
    
    # Check that the output file path was logged
    output_file_name = "test_exp_001_run_v1_pending_candidate_1.json"
    assert run1['output_files'][0].endswith(output_file_name)

    # Check the 'completed' run (it should be unchanged)
    run2 = updated_config['experiments'][0]['runs'][1]
    assert run2['status'] == 'completed'
    assert 'metrics' not in run2 # Proves it was skipped

    # Check that the actual output file was created
    output_path = tmp_path / 'llm_outputs' / output_file_name
    assert output_path.exists()
    
    # Check the content of the output file
    file_content = output_path.read_text(encoding="utf-8")
    assert file_content == '{"summary": "This is the mock API response"}'

    print("\nIntegration test passed! 'main' correctly updated the YAML and saved the output file.")
