"""
Probe the Gemini retry policy before spending pipeline quota.

Why this exists:
    On 2026-09-24, google-api-core's default retry on generate_content
    (503 only, deadline=600s, backoff capped at 10s) turned a 503 burst into
    ~66 requests per call. Stacked under Prefect retries, that used 422/500
    RPD. make_api_call now uses a capped policy (REQUEST_OPTIONS: timeout=30s,
    ~6 attempts). This script verifies that policy without running a pipeline.

Design:
    Imports REQUEST_OPTIONS from generate_questions rather than redeclaring
    it, so the probe tests the config the pipeline actually uses. A copy
    here could drift from the real one, and a probe of the copy would
    still pass.

Modes:
    --offline   No API call, zero quota. Feeds the retry policy a function
                that always raises ServiceUnavailable (503), and reports how
                many attempts it made and how long it took. This is the only
                way to exercise the retry path, since a real 503 can't be
                triggered on demand.
                Expect: RetryError, ~6-8 attempts in ~30s (jitter varies the
                count). Before the fix, this ran ~10 min and made ~66 attempts.

    (default)   One live request with the real REQUEST_OPTIONS. Confirms the
                SDK accepts the options and the call returns.
                Expect: prints the policy (timeout=30), response "OK", token
                usage. Dashboard RPD should go up by exactly 1. More than 1
                means retries fired.

Usage (from repo root, same way generate_questions.py is run):
    python scripts/pipelines/generate_questions/probe_api.py --offline
    python scripts/pipelines/generate_questions/probe_api.py

    If 'src' fails to import, prefix with PYTHONPATH=.

Run --offline first (free), then the live probe, before any pipeline run.
"""

import sys
import time
from google.api_core import exceptions as core_exceptions
from scripts.pipelines.generate_questions.generate_questions import (configure_api, 
                                                                     CONFIG_PATH, 
                                                                     REQUEST_OPTIONS, 
                                                                     SDK_RETRY)

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
    def always_503():
        attempts["n"] += 1
        raise core_exceptions.ServiceUnavailable("fake")
    t0 = time.perf_counter()
    try:
        SDK_RETRY(always_503)()
    except Exception as e:
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
    import google.generativeai as genai
    
    configure_api(CONFIG_PATH)
    print("retry:", SDK_RETRY, "| timeout:", REQUEST_OPTIONS.get("timeout"))
    model = genai.GenerativeModel("gemini-3.1-flash-lite")  # type: ignore
    t0 = time.perf_counter()
    resp = model.generate_content("Reply with OK.", request_options=REQUEST_OPTIONS)
    print(f"{time.perf_counter() - t0:.2f}s | {resp.text.strip()} | {resp.usage_metadata}")

if __name__ == "__main__":
    if "--offline" in sys.argv:
        offline()
    else:
        live()
