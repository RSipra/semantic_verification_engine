"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for the llm service module
-----------------------------------------------------------------------    
"""

import logging
import pytest
from engine.dto import LLMJudgeResponse
import engine.services.llm_service as llms

## Setup: fixtures and mocks

@pytest.fixture(scope="session", autouse=True)
def enable_logging():
    """
    Pytest fixture that enables debug-level logging for tests.

    Automatically configures logging so that debug output from the
    evaluation and LLM service layers is visible during test runs.
    Applies to all tests in the session due to autouse=True.
    """
    logging.basicConfig(level=logging.DEBUG)

# LLM mock to simulate Gemini client behavior for unit tests
@pytest.fixture
def sample_eval_request():
    """Reusable evaluation request payload for LLM service tests."""

    return {
        "question": "Who is Harry Potter?",
        "gold_answer": "Harry Potter",
        "player_answer": "Harry Potter",
        "answer_variations": ["The Boy Who Lived"],
        "source_quote": None,
        "explanation": "Harry is the protagonist.",
        "system_prompt": llms.SYSTEM_PROMPT_FR_SPECIALIST,
        "delay_seconds": 0.0,
    }

VALID_LLM_JSON = """
{
    "is_correct": true,
    "quiz_host_response": "Correct!",
    "evaluation_reasoning": "Player identified the correct entity."
}
"""
class FakeLLM:
    """
    Lightweight mock of a Gemini-like LLM client. This class simulates 
    the minimal interface used by the LLM service layer:
    - generate_content(...)
    - returns an object with a `.text` attribute

    It is used to test:
    - successful LLM responses
    - cascade/fallback logic
    - failure handling
    - call counting (for retry / cascade validation)

    Attributes:
        response_text (str | None): The fake LLM output returned on success.
        should_fail (bool): If True, simulate a network/API failure.
        call_count (int): Tracks how many times generate_content is called.
    """

    def __init__(self, response_text: str | None, should_fail: bool = False, error_type:str= "transient"):
        # configure mock behavior
        self.response_text = response_text
        self.should_fail = should_fail
        self.error_type = error_type
        # used to validate retry / cascade logic
        self.call_count = 0

    def generate_content(self, *args, **kwargs):
        """ Simulates Gemini's generate_content() method"""
        self.call_count += 1  # track cascade logic

        # simulate API failure path
        if self.should_fail:
            if self.error_type not in ("transient", "fatal"):
                raise ValueError("error_type must be 'transient' or 'fatal'")
            if self.error_type == "transient":
                raise Exception("timeout: simulated failure")
            else:
                raise Exception("invalid request: simulated fatal error")

        # successful call: # simulate API response object
        class FakeResponse:
            """minimal response object with only the fields used by the service (.text)"""
            def __init__(self, text):
                self.text = text
        return FakeResponse(self.response_text)    

## 1: Building prompt context

#1. happy path, build prompt context properly
def test_build_prompt_context_happy_path_legacy():
    """Generate valid promt context with correct input provided with legacy question"""
    gold_answer = "harry potter"
    answer_variations = ['harry potter', 'the boy who lived', 'chosen one']
    explanation = "harry is the protagonist of the Harry Potter series"
    source_quote = None   # pydantic model allows str or None

    prompt_context = llms._build_prompt_context(gold_answer, answer_variations, explanation, source_quote)

    assert "[GROUND TRUTH CONTEXT]" in prompt_context
    assert "Gold Answer: harry potter" in prompt_context
    assert "Explanation: harry is the protagonist of the Harry Potter series" in prompt_context
    assert "Source Text Quote" not in prompt_context
    assert "Acceptable Variations:" in prompt_context
    for v in answer_variations:
        assert v in prompt_context    

def test_build_prompt_context_happy_path_synthetic():
    """Generate valid promt context with correct input provided with synthetic question"""
    gold_answer = "harry potter"
    answer_variations = ['harry potter', 'the boy who lived', 'chosen one']
    explanation = "harry is the protagonist of the Harry Potter series"
    source_quote = "this is a quote from book 1"

    prompt_context = llms._build_prompt_context(gold_answer, 
                                                answer_variations, 
                                                explanation, 
                                                source_quote)

    assert "[GROUND TRUTH CONTEXT]" in prompt_context
    assert "Gold Answer: harry potter" in prompt_context
    assert "Acceptable Variations:" in prompt_context
    for v in answer_variations:
        assert v in prompt_context 
    assert "Explanation: harry is the protagonist of the Harry Potter series" in prompt_context
    assert 'Source Text Quote: "this is a quote from book 1"' in prompt_context
        
# edge case: empty answer variation list:

def test_build_prompt_context_empty_ans_variations():
    """Ensure empty answer_variations does not appear in prompt context"""
            
    gold_answer = "harry potter"
    answer_variations = []
    explanation = "harry is the protagonist of the Harry Potter series"
    source_quote = None   # pydantic model allows str or None

    prompt_context = llms._build_prompt_context(gold_answer, 
                                                answer_variations, 
                                                explanation, 
                                                source_quote)

    assert "Acceptable Variations:" not in prompt_context
    assert "Source Text Quote" not in prompt_context

## 2: call LLM judge 

# happy path: successful call to the primary model
def test_call_llm_judge_happy_path(monkeypatch, sample_eval_request):
    """LLM judge returns valid structured response on successful API call."""
    
    # Arrange
    # 1. configure fake llm behavior with simulated correct response
    fake_llm = FakeLLM(response_text=VALID_LLM_JSON)
    
    # 2. replace Gemini model constructor with fake
    monkeypatch.setattr(
        llms.genai,
        "GenerativeModel",
        lambda *args, **kwargs: fake_llm  # return fake llm response
    )

   # Act
    payload, model_used, _, success = llms.call_llm_judge(**sample_eval_request)
    
    assert payload.is_correct is True
    assert model_used == llms.PRIMARY_MODEL
    assert success is True

# happy path: primary model fails cascade to fallback model successful 
def test_call_llm_judge_cascade_to_fallback_model_success(monkeypatch, sample_eval_request):
    """
    LLM judge returns valid structured response on successful API call to fallback 
    model. testing cascade where the primary model call failed.
    """
    # configure cascade model behaviour:
    responses = [
        FakeLLM(response_text=None, should_fail=True),            # primary model fails
        FakeLLM(response_text=VALID_LLM_JSON, should_fail=False)  # fallback successul
    ]
    
    # simulate to sequential API calls to test how the llm call cascade loop responds
    def fake_constructor(*args, **kwargs):
        return responses.pop(0)
    
    # fake model constructs
    monkeypatch.setattr(llms.genai, "GenerativeModel", fake_constructor)
    
    # act
    payload, model_used, _, success = llms.call_llm_judge(**sample_eval_request)

    assert success is True
    assert model_used == llms.FALLBACK_MODEL
    assert payload.is_correct is True

# unhappy path: cacade to primary / fallback fails (graceful fallback) 
def test_call_llm_judge_cascade_all_models_fail(monkeypatch, sample_eval_request):
    """
    LLM judge returns failed api call response after API call to fallback 
    model is unsucessful. testing cascade where the primary model call failed earlier.
    """
    # configure cascade model behaviour:
    primary_llm = FakeLLM(response_text="primary fail", should_fail=True)
    fallback_llm = FakeLLM(response_text="fallback fail", should_fail=True)

    responses = [primary_llm, fallback_llm]
    
    # simulate to sequential API calls to test how the llm call cascade loop responds
    def fake_constructor(*args, **kwargs):
        return responses.pop(0)
    
    # fake model constructs
    monkeypatch.setattr(llms.genai, "GenerativeModel", fake_constructor)
    
    # act
    payload, model_used, _, success = llms.call_llm_judge(**sample_eval_request)

    # confirm that the correct response after cascade fall is given
    assert success is False
    assert model_used == llms.FALLBACK_MODEL
    assert isinstance(payload, LLMJudgeResponse)
    assert payload.is_correct is False
    assert primary_llm.call_count == 1
    assert fallback_llm.call_count == 1
    
# unhappy path: non-transient / fatal error (fail fast) / not continue with cascade
def test_call_llm_judge_non_transient_fail_fast(monkeypatch, sample_eval_request):
    """LLM should run fail fast error for non-transient error"""
    fake_llm = FakeLLM(response_text="invalid response", should_fail=True, error_type="fatal")

    def fake_constructor(*args, **kwargs):
        return fake_llm

    monkeypatch.setattr(llms.genai, "GenerativeModel", fake_constructor)

    payload, model_used, _, success = llms.call_llm_judge(**sample_eval_request)

    assert success is False
    assert model_used == llms.PRIMARY_MODEL
    assert isinstance(payload, LLMJudgeResponse)
    assert payload.is_correct is False    

## warmup call

def test_warmup_calls_model(monkeypatch):
    """The method establishes connection and recieves warmup response"""
    # correct response from fake model 
    fake_llm = FakeLLM(response_text=VALID_LLM_JSON)
    # fake model instance
    monkeypatch.setattr(llms.genai,"GenerativeModel",lambda *args, **kwargs: fake_llm)

    # act: setup the warmup connection
    llms.warmup_llm_connection()

    # should only make one call
    assert fake_llm.call_count == 1
    
def test_signal_llm_health_mapping():
    assert llms.signal_llm_health({"success": True}) == llms.llm_warmup_health.OK
    assert llms.signal_llm_health({"success": False, "error": "timeout"}) == llms.llm_warmup_health.DEGRADED
    assert llms.signal_llm_health({"success": False, "error": "boom"}) == llms.llm_warmup_health.FAILED    
    
## latency wrapper

# happy path 
def test_track_eval_latency_injects_execution_time():
    """
    Verifies that the `track_eval_latency` decorator correctly measures
    execution time and injects it into the returned evaluator result object.

    This test uses a lightweight dummy evaluator to ensure:
    - The wrapped function executes normally
    - A result object is returned unchanged in identity
    - The `execution_time_sec` attribute is populated with a non-null value

    This validates the decorator’s core responsibility of adding observability
    metadata without altering functional output.
    """
    class DummyResult:
        """Minimal stand-in object used to simulate an evaluator return value."""
        def __init__(self):
            self.execution_time_sec = None

    @llms.track_eval_latency
    def fake_eval():
        return DummyResult()

    result = fake_eval()

    assert isinstance(result, DummyResult)
    assert result.execution_time_sec is not None
    assert result.execution_time_sec >= 0   
