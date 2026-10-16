"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementaiton: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
Behavioral contract tests for the llm service module
-----------------------------------------------------------------------
How the fakes work:
- The service talks to Gemini only through the module-level `llms.client`.
- Tests swap that object for a FakeClient whose `.models.generate_content`
  plays back a scripted list of outcomes, one per call:
    - a str / None  -> returned as a response with that `.text`
    - an Exception  -> raised (simulates API / network failures)
- Every call is recorded, so tests assert which models were called, in
  which order, and with what request config.
- Errors are real SDK / httpx exception types, because the service now
  classifies errors by type and status code, not by message text.    
"""

import logging
import httpx
import pytest
from google.genai import errors
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

# suspend backoff delays so tests run quickly
@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    """
    Zero the cascade sleeps so failure-path tests run instantly.
 
    The service reads these module constants at call time, so patching
    them here takes effect inside call_llm_judge. (delay_seconds is
    already 0.0 in sample_eval_request.)
    """
    monkeypatch.setattr(llms, "TRANSIENT_BACKOFF", 0.0)
    monkeypatch.setattr(llms, "ERROR_COOLDOWN", 0.0)    

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

# successful call: # simulate API response object
class FakeResponse:
    """minimal response object with only the fields used by the service (.text)"""
    def __init__(self, text):
        self.text = text

# standin for the Gemini client model interface, used by the service to call LLMs
class FakeModels:
    """
    Stand-in for `client.models`. Plays back one scripted outcome per call
    and records each call's arguments.
    """

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)
        self.calls: list[dict] = []

    # keyword-only, mirroring how the service calls the real SDK
    def generate_content(self, *, model, contents, config=None):
        "create the model call record"
        self.calls.append({"model": model, "contents": contents, "config": config})

        if not self._outcomes:
            # pytest.fail raises a BaseException subclass, so the service's
            # `except Exception` cannot swallow it: an unexpected extra call
            # fails the test loudly instead of being classified as an error.
            pytest.fail(f"Unexpected extra LLM call (call #{len(self.calls)}, model={model})")

        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)

    @property
    def models_called(self) -> list[str]:
        """Shortcut to get the list of model names used in calls, in order."""
        return [call["model"] for call in self.calls]

#  Stand-in for genai.Client: an empty shell that only exposes `.models`.
class FakeClient:
    """
    Stand-in for genai.Client: an empty shell that only exposes `.models`,
    so the service's `client.models.generate_content(...)` call resolves.
 
    Why fake the client and not just `.models`:
    - The service reaches the LLM only through the module-level `llms.client`,
      so that object is the single patch point for tests.
    - The real client is created at import time and owns the API key and
      connection pool; replacing it whole guarantees no test touches the
      real network.
 
    No transport here: FakeModels simulates the entire LLM call.
    """
    def __init__(self, outcomes):
        self.models = FakeModels(outcomes)

@pytest.fixture
def install_fake_client(monkeypatch):
    """
    Factory fixture: install_fake_client(outcome_1, outcome_2, ...) swaps
    `llms.client` for a FakeClient scripted with those outcomes and returns it.
    """
    def _install(*outcomes) -> FakeClient:
        fake = FakeClient(outcomes)
        monkeypatch.setattr(llms, "client", fake)
        return fake
    return _install

def api_error(code: int) -> errors.APIError:
    """
    Build a real google-genai API error for a given HTTP status code.
    4xx -> ClientError, 5xx -> ServerError (both subclass APIError).
    If the SDK's constructor signature changes, fix it here only.
    """
    body = {"error": {"code": code, "message": f"simulated {code}", "status": "SIMULATED"}}
    error_cls = errors.ServerError if code >= 500 else errors.ClientError
    return error_cls(code, body)

EC = llms.ErrorClass
HEALTH = llms.LlmWarmupHealth                      

## 1: Building prompt context

#1. happy path, build prompt context properly
def test_build_prompt_context_happy_path_legacy():
    """Generate valid promt context with correct input provided with legacy question"""
    gold_answer = "harry potter"
    answer_variations = ['harry potter', 'the boy who lived', 'chosen one']
    explanation = "harry is the protagonist of the Harry Potter series"
    source_quote = None   # pydantic model allows str or None

    prompt_context = llms._build_prompt_context(
        gold_answer, 
        answer_variations,
        explanation,
        source_quote
        )

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

## 2: Error classification (single source of truth for warmup + judge)

# explicitly check the status code sets to ensure they match the intended classification
def test_status_code_contract():
    """
    Pins the intended classification. The parametrized tests derive their
    cases from the constants, so they can't detect a code being removed;
    this test can.
    """
    assert llms.TRANSIENT_CODES == {429, 500, 502, 503, 504}
    assert llms.FAIL_FAST_CODES == {400, 401, 403, 404}

# make sure the two status code sets dont overlap, so that the service 
# can classify errors unambiguously
def test_status_code_sets_do_not_overlap():
    """A status code cannot be both transient and fail-fast."""
    assert llms.TRANSIENT_CODES.isdisjoint(llms.FAIL_FAST_CODES)

# confirm the error codes are classified correctly as transient
# SDK uses codes and not strings 
@pytest.mark.parametrize("code", sorted(llms.TRANSIENT_CODES))
def test_classify_error_transient_codes(code):
    """
    Every status code in TRANSIENT_CODES (429, 5xx) is classified TRANSIENT,
    so the judge cascades to the fallback model and warmup reports DEGRADED.
    Parametrized from the constant, so adding a code is covered automatically.
    """
    assert llms._classify_error(api_error(code)) is EC.TRANSIENT

# confirm the error codes are classified correctly as fail-fast
# SDK uses codes and not strings 
@pytest.mark.parametrize("code", sorted(llms.FAIL_FAST_CODES))
def test_classify_error_fail_fast_codes(code):
    """
    Every status code in FAIL_FAST_CODES (400, 401, 403, 404) is classified
    FAIL_FAST: retrying cannot help, so the judge stops without cascading.
    Parametrized from the constant, so adding a code is covered automatically.
    """
    assert llms._classify_error(api_error(code)) is EC.FAIL_FAST

# test for remaning cases: no error, read timeout, connect error, unlisted API code, non-API exception
@pytest.mark.parametrize("error, expected", [
    pytest.param(None, EC.NONE, id="no-error"),
    pytest.param(httpx.ReadTimeout("simulated timeout"), EC.TRANSIENT, id="read-timeout"),
    pytest.param(httpx.ConnectError("simulated connect error"), EC.TRANSIENT, id="connect-error"),
    pytest.param(api_error(418), EC.UNEXPECTED, id="unlisted-api-code"),
    pytest.param(ValueError("our bug"), EC.UNEXPECTED, id="non-api-exception"),
])
def test_classify_error_other_cases(error, expected):
    """
    Cases outside the status-code sets:
    - no error -> NONE (the success category)
    - network failures (timeouts, connection errors) -> TRANSIENT, matched by
      exception type since they carry no HTTP status code
    - an API code in neither set, or any non-API exception -> UNEXPECTED
      (fail-closed: unknown errors fail fast instead of being retried)
    """
    assert llms._classify_error(error) is expected

## 3: call LLM judge 

# happy path: successful call to the primary model
def test_call_llm_judge_happy_path(install_fake_client, sample_eval_request):
    """LLM judge returns valid structured response on successful API call."""

    fake = install_fake_client(VALID_LLM_JSON)

    payload, model_used, latency, success = llms.call_llm_judge(**sample_eval_request)

    assert success is True
    assert payload.is_correct is True
    assert model_used == llms.PRIMARY_MODEL
    assert latency >= 0
    assert fake.models.models_called == [llms.PRIMARY_MODEL]

# happy path: verify the request sent to the LLM judge contains the expected prompt and config
def test_call_llm_judge_sends_expected_requests(install_fake_client, sample_eval_request):
    """The request carries the prompt content and the judge's config."""
    fake = install_fake_client(VALID_LLM_JSON)

    llms.call_llm_judge(**sample_eval_request)

    call = fake.models.calls[0]
    config = call["config"]
    assert sample_eval_request["question"] in call["contents"]
    assert sample_eval_request["player_answer"] in call["contents"]
    assert config.system_instruction == sample_eval_request["system_prompt"]
    assert config.temperature == llms.LLM_JUDGE_TEMPERATURE
    assert config.response_mime_type == "application/json"
    assert config.response_schema is LLMJudgeResponse
    assert config.http_options.timeout == 60_000  # milliseconds

# happy path: verify that the LLM judge can handle JSON wrapped in markdown fences
def test_call_llm_judge_parses_markdown_fenced_json(install_fake_client, sample_eval_request):
    """JSON wrapped in ```json fences is cleaned before validation."""
    install_fake_client(f"```json\n{VALID_LLM_JSON}\n```")

    payload, _, _, success = llms.call_llm_judge(**sample_eval_request)

    assert success is True
    assert payload.is_correct is True

TRANSIENT_ERROR_FACTORIES = [
    pytest.param(lambda: api_error(429), id="429-rate-limit"),
    pytest.param(lambda: api_error(503), id="503-unavailable"),
    pytest.param(lambda: api_error(500), id="500-server-error"),
    pytest.param(lambda: httpx.ReadTimeout("simulated timeout"), id="read-timeout"),
    pytest.param(lambda: httpx.ConnectError("simulated connect error"), id="connect-error"),
    ]

# unhappy path: transient error on primary model -> fallback model is tried and succeeds
@pytest.mark.parametrize("make_error", TRANSIENT_ERROR_FACTORIES)
def test_call_llm_judge_transient_error_cascades_to_fallback(
        install_fake_client, sample_eval_request, make_error):
    """Transient failure on primary -> fallback model is tried and succeeds."""
    fake = install_fake_client(make_error(), VALID_LLM_JSON)
 
    payload, model_used, _, success = llms.call_llm_judge(**sample_eval_request)
 
    assert success is True
    assert payload.is_correct is True
    assert model_used == llms.FALLBACK_MODEL
    assert fake.models.models_called == [llms.PRIMARY_MODEL, llms.FALLBACK_MODEL]
    
# unhappy path: cacade to primary / fallback fails (graceful fallback) 
def test_call_llm_judge_transient_all_models_fail(install_fake_client, sample_eval_request):
    """
    LLM judge returns failed api call response after API call to fallback 
    model is unsucessful. testing cascade where the primary model call failed earlier.
    """
    fake = install_fake_client(api_error(429), api_error(503))

    payload, model_used, latency, success = llms.call_llm_judge(**sample_eval_request)

    # confirm that the correct response after cascade fall is given
    assert success is False
    assert model_used == llms.FALLBACK_MODEL
    assert isinstance(payload, LLMJudgeResponse)
    assert payload.is_correct is False
    assert "All LLM tiers failed" in payload.evaluation_reasoning
    assert latency == 0.0
    assert fake.models.models_called == [llms.PRIMARY_MODEL, llms.FALLBACK_MODEL]

# unhappy path: transient error on primary model -> fallback model fails unexpectedly
def test_call_llm_judge_transient_then_unexpected_fails_fast_on_fallback(
        install_fake_client, sample_eval_request):
    """
    Primary fails transiently, so the judge cascades; the fallback then fails
    unexpectedly, so the judge fails fast there. The returned model is the
    fallback (where it stopped), and the outcome is the fail-fast payload,
    not the cascade-exhausted one.
    """
    fake = install_fake_client(api_error(503), RuntimeError("unexpected boom"))

    payload, model_used, _, success = llms.call_llm_judge(**sample_eval_request)

    assert success is False
    assert model_used == llms.FALLBACK_MODEL
    assert "System error: unexpected boom" in payload.evaluation_reasoning
    assert "All LLM tiers failed" not in payload.evaluation_reasoning
    assert fake.models.models_called == [llms.PRIMARY_MODEL, llms.FALLBACK_MODEL]    

# unhappy path: non-transient / fatal error (fail fast) / not continue with cascade
@pytest.mark.parametrize("code", sorted(llms.FAIL_FAST_CODES))
def test_call_llm_judge_fail_fast_does_not_cascade(install_fake_client, sample_eval_request, code):
    """LLM should run fail fast error for non-transient error"""
    fake = install_fake_client(api_error(code))  # a second call would pytest.fail

    payload, model_used, latency, success = llms.call_llm_judge(**sample_eval_request)

    assert success is False
    assert model_used == llms.PRIMARY_MODEL
    assert isinstance(payload, LLMJudgeResponse)
    assert payload.is_correct is False
    assert latency == 0.0
    assert fake.models.models_called == [llms.PRIMARY_MODEL]

# unhappy path: unexpected error (fail fast) / not continue with cascade
@pytest.mark.parametrize("outcome", [
    pytest.param(None, id="empty-response"),
    pytest.param("not json at all", id="invalid-json"),
    pytest.param(RuntimeError("unexpected boom"), id="unexpected-exception"),
    pytest.param(api_error(418), id="unlisted-api-code"),
    pytest.param('{"unexpected_field": 1}', id="schema-mismatch"),
    ])

def test_call_llm_judge_unexpected_error_fails_fast(
        install_fake_client, sample_eval_request, outcome):
    """
    Unexpected failures (empty/invalid response, unknown errors) fail fast.
    Documents the current design choice: these do NOT try the fallback model.
    """
    fake = install_fake_client(outcome)

    payload, model_used, _, success = llms.call_llm_judge(**sample_eval_request)

    assert success is False
    assert payload.is_correct is False
    assert model_used == llms.PRIMARY_MODEL
    assert fake.models.models_called == [llms.PRIMARY_MODEL]

## warmup call + health signal

# get the expected signal keys from the WarmupSignals (TypedDict) annotations,
# derived to match the system signal dict schema (SOT)
EXPECTED_SIGNAL_KEYS = set(llms.WarmupSignals.__annotations__)

# happy path: warmup call succeeds and returns the expected signal dict
def test_warmup_call_success_returns_ok_signals(install_fake_client):
    """The method establishes connection and recieves warmup response"""
    # correct response from fake model 
    fake = install_fake_client(VALID_LLM_JSON)
    signals = llms.warmup_llm_connection()

    # should only make one call
    assert fake.models.models_called == [llms.PRIMARY_MODEL]
    assert set(signals) == EXPECTED_SIGNAL_KEYS
    assert signals["event_type"] == "llm_warmup"
    assert signals["success"] is True
    assert signals["error"] is None
    assert signals["error_type"] is None
    assert signals["error_code"] is None
    assert signals["error_class"] is EC.NONE
    assert signals["health"] is HEALTH.OK
    assert signals["duration_sec"] >= 0

# warmup call tests for different error types and the expected health signal mapping
@pytest.mark.parametrize(
    "error, expected_class, expected_health, expected_code", 
    [
        pytest.param(api_error(503), EC.TRANSIENT, HEALTH.DEGRADED, 503, id="503-degraded"),
        pytest.param(httpx.ReadTimeout("simulated timeout"), EC.TRANSIENT, HEALTH.DEGRADED, None,
                    id="timeout-degraded"),
        pytest.param(api_error(401), EC.FAIL_FAST, HEALTH.FAILED, 401, id="401-failed"),
        pytest.param(RuntimeError("unexpected boom"), EC.UNEXPECTED, HEALTH.FAILED, None,
                    id="unexpected-failed"),
    ])

# unhappy path: warmup call fails with different error types with correct health signal
def test_warmup_failure_classifies_health(install_fake_client, error,
                                          expected_class, expected_health,
                                          expected_code):
    """Failed warmup: same signal dict shape, health derived from the error class."""
    install_fake_client(error)

    signals = llms.warmup_llm_connection()

    assert set(signals) == EXPECTED_SIGNAL_KEYS
    assert signals["success"] is False
    assert signals["error_class"] is expected_class
    assert signals["health"] is expected_health
    assert signals["error_code"] == expected_code
    assert signals["error_type"] == type(error).__name__
    assert signals["error"] is not None
    assert signals["duration_sec"] >= 0  

# confirm that every ErrorClass has a corresponding health mapping
def test_every_error_class_has_a_health_mapping():
    """Adding an ErrorClass member without a health mapping fails here."""
    assert set(llms._HEALTH_BY_CLASS) == set(EC)

# test: confirm errors are classified to correct health signal (trasient, fail-fast, unexpected)
@pytest.mark.parametrize(
    "error", [
        pytest.param(None, id="success"),
        pytest.param(api_error(429), id="transient"),
        pytest.param(api_error(400), id="fail-fast"),
        pytest.param(RuntimeError("boom"), id="unexpected"),
    ]
)

# confirm error is correctly classified to health signal
def test_signal_llm_health_matches_record(error):
    """signal_llm_health reads the record and agrees with its stored health."""
    signals = llms._build_warmup_signals("test-model", 0.0, error)
    assert llms.signal_llm_health(signals) is signals["health"]
 
# unhappy path: corrupted record maps to FAILED health 
def test_signal_llm_health_fails_closed_on_unknown_class():
    """A corrupted record (e.g. loaded from logs) maps to FAILED, not a crash."""
    signals = llms._build_warmup_signals("test-model", 0.0)
    corrupted = {**signals, "error_class": "not-a-real-class"}
    assert llms.signal_llm_health(corrupted) is HEALTH.FAILED  # type: ignore[arg-type]

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
