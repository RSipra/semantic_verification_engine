"""
Probe the Gemini retry policy before spending pipeline quota.

Why this exists:
    On 2026-09-24, the old SDK's google-api-core default retry (503 only,
    deadline=600s) turned a 503 burst into ~66 requests per call; stacked under
    Prefect retries that used 422/500 RPD. Since the google-genai migration the
    SDK-level policy is HTTP_OPTIONS (client): 503 only, 5 attempts, 1s/x1.3/10s
    backoff + jitter, per-request timeout 60 s. This script measures that policy
    without running a pipeline.

Design:
    Imports SDK_RETRY / HTTP_OPTIONS from generate_questions rather than
    redeclaring them, so the probe tests the config the pipeline actually uses. A copy
    here could drift from the real one, and a probe of the copy would
    still pass.

Modes:
    --offline   No network, zero quota. Sends a real SDK call through a fake
                HTTP transport (httpx.MockTransport) that always answers 503,
                and counts the requests the SDK makes before giving up. This
                exercises the SDK's actual retry path; a real 503 can't be
                triggered on demand.
                Expect: ServerError, 5 attempts in ~8–9 s
    (default)   One live request through the pipeline's configured client.
                Expect: prints the policy, response "OK", token usage.
                Dashboard RPD should go up by exactly 1; more than 1 means
                SDK retries fired.

Usage (from repo root, same way generate_questions.py is run):
    python -m scripts.pipelines.generate_questions.probe_api --offline
    python -m scripts.pipelines.generate_questions.probe_api

Run --offline first (free), then the live probe, before any pipeline run.
"""

import sys
import time
import httpx
from prefect import flow
from google import genai
from google.genai import errors, types
from scripts.pipelines.generate_questions.generate_questions import (configure_api, 
                                                                     CONFIG_PATH, 
                                                                     HTTP_OPTIONS, 
                                                                     SDK_RETRY)
@flow
def offline():
    """
    Exercise the retry path with a simulated 503, making no API calls.

    Passes REQUEST_OPTIONS["retry"] a function that always raises
    ServiceUnavailable, the only exception the policy retries. The policy
    retries with backoff until its 30s timeout expires, then raises
    RetryError. Prints the number of attempts and the elapsed time.

    Why:
        A real 503 can't be triggered on demand, so a live call never runs
        the retry path. This is the only quota-free check that the cap works.

    Expect:
        RetryError, ~8 attempts in ~13s. Backoff jitter varies the count.
        Under the old SDK default (deadline=600s), this would run ~120
        attempts over ~10 min. Anything near that means the cap isn't
        applied.
    """
    attempts = {"n": 0}
    def always_503(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503, json={"error": {"code": 503, "message": "fake",
                                                   "status": "UNAVAILABLE"}})

    # same retry policy + timeout as the pipeline, but HTTP goes to the fake transport
    fake_client = genai.Client(
        api_key="offline-probe",
        http_options=types.HttpOptions(
            timeout=HTTP_OPTIONS.timeout,
            retry_options=SDK_RETRY,
            client_args={"transport": httpx.MockTransport(always_503)},  # CONFIRM field name
        ),
    )
    t0 = time.perf_counter()
    try:
        fake_client.models.generate_content(model="gemini-3.1-flash-lite", contents="probe")
    except errors.APIError as e:
        print(f"{type(e).__name__} | {attempts['n']} attempts in {time.perf_counter() - t0:.1f}s")

def live():
    """
    Make one real generate_content call using the pipeline's REQUEST_OPTIONS.

    Configures the API, prints the retry policy and timeout being used, and
    sends a minimal prompt ("Reply with OK."). Prints latency, the response
    text, and token usage.

    Why:
        Confirms the SDK accepts the request options and the call completes
        before any pipeline run spends quota.

    Expect:
        Printed policy shows timeout=30. Response "OK". Dashboard RPD goes
        up by exactly 1. More than 1 means a 503 triggered retries.

    Cost:
        1 request normally; at most ~6-8 if the call hits 503s, bounded by
        the 30s timeout.
    """    
    client = configure_api(CONFIG_PATH)
    print("retry:", SDK_RETRY, "| timeout (ms):", HTTP_OPTIONS.timeout)
    t0 = time.perf_counter()
    resp = client.models.generate_content(model="gemini-3.1-flash-lite", contents="Reply with OK.")
    print(f"{time.perf_counter() - t0:.2f}s | {(resp.text or '').strip()} | {resp.usage_metadata}")

if __name__ == "__main__":
    if "--offline" in sys.argv:
        offline()
    else:
        live()
