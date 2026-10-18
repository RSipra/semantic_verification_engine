
# Engineering Backlog

## Now / Next
1. Test suite cleanup (§1)
2. Pipeline migration → remove old SDK (§8, §9)
3. Validate main in a container build (§10)
---

## 1. Testing
- [ ] Controller unit tests (turn lifecycle, scoring)
- [ ] Integration test: full game loop (mocked input)
- [ ] SessionReport serialization roundtrip test
- [ ] Edge case replay runner for evaluator regression
- [X] llm_service test suite rewritten for google-genai (fake client, real SDK/httpx errors, classifier + cascade + warmup signals,   status-code contract test) — PR #10
- [ ] **Test suite cleanup PR** — pre-existing failures unrelated to the SDK migration (establish a green baseline before the offline refactor):
  - 6 files fail at collection: stale imports from moved modules (`test_experiment_prompt`, `test_gamecontroller`, `test_gameview`, `test_question`, `test_trivia`, `test_warmup`)
  - `test_structured_evaluators`: 19 failures — tests call old private names (`_check_numeric_answer` etc.); functions are now public
  - `test_player_str`: fails on Python 3.12 only (str-mixin enum formatting changed) — build expected string from `house.value`
  - `test_router::test_dispatch_log_emits_info`: expected `extra` missing the new `"stage": "router"` key
  - `test_ex_evaluator::test_ex_evaluator_with_ambiguous_incorrect_answer`: `@patch` / fixture argument order (patch args must come first)
- [ ] Run the game locally the same way the container does (`PYTHONPATH=src python src/game_app/main.py`), not only via `-m` / pytest — the container found a bug local runs missed

## 2. Observability
- [ ] Add main and controller lifecycle events
- [ ] Add latency metrics for evaluator tiers
- [ ] Add AI judge usage metrics
- [ ] Add session analytics reporting
- [ ] Add JSONL/structured persistence layer for SessionReport / SessionAggregates
- [ ] **Integrate warmup health signal into the controller** — startup already collects `WarmupSignals` (health: OK / DEGRADED / FAILED); nothing acts on it yet
  - Decide how the LLM entry fits `system_signals` (other components use `status`; the LLM entry is the full record with `health`)
- [ ] **Controller observability design** — what the controller consumes, per-call vs per-attempt events for the judge cascade, whether a successful fallback counts as DEGRADED, where events go
- [ ] Then generalize `WarmupSignals` → `LLMCallSignals` (event_type: warmup | judge) reusing `_classify_error` (deferred by design; see NOTE in `llm_service`)

#### (Future Phases)

- [ ] Evaluate OpenTelemetry for distributed tracing once system moves toward FastAPI architecture
- [ ] Evaluate Sentry for structured error tracking post-stabilization
- [ ] Consider dashboarding/metrics layer (Grafana or equivalent) for aggregated session analytics

#### General Note
- Tooling and external observability frameworks (OpenTelemetry, Sentry, dashboards, APM tools) will be evaluated only once the system is stable, containerized, and runtime behavior is consistent.
- Current priority is core system stability, reproducible execution, and demo readiness.

---

## 3. Architecture
- [ ] Move notebook_support outside src
- [ ] Audit runtime dependencies after notebook_support separation.
  - Generate clean production requirements.txt
  - Verify container builds using runtime dependencies only
- [ ] Evaluate migration from CLI loop → FastAPI service layer
- [ ] FastAPI service layer with startup caching + lazy loading
  - Introduce service-level startup lifecycle (model + dataset preloading)
  - Cache SBERT/LLM resources across sessions to eliminate cold-start latency
  - Convert system_signals into persistent runtime state for readiness tracking (INIT → WARMING → READY)
  - Decouple session warmup from application startup to enable non-blocking intro UX
- [ ] Introduce event-based controller logging (optional future refactor)
- [ ] **Single LLM gateway (ADR proposed)** — one core primitive owning the provider boundary (client, error classification, retry policy, observability hooks) + domain wrappers (runtime judge, offline generation). Extract the core from `llm_service` during the pipeline migration, against two real callers
- [ ] Decide `src/core` vs `src/engine/services` location for the shared LLM core
- [ ] Tracer lab imports shared functions from `llm_service` instead of duplicating them

---

## 4. Performance
- [X] SBERT cold start benchmarking
- [X] LLM warmup latency measurement in container
  - VM container (google-genai), cold call, n=4: 4.6 / 5.9 / 11.2 / 12.4 s (median ~8.6 s)
  - ~83 output tokens per call, so generation is negligible; variance is provider-side
    (queueing / time-to-first-token), consistent with LLM latency as a soft target
- [ ] Evaluate caching strategy for repeated embeddings
- [X] Optimize Dockerfile dependency resolution and layer bloat (Immediate Fix)
  - Enforce --extra-index-url https://download.pytorch.org/whl/cpu on secondary requirements installation to prevent pip from pulling default GPU/CUDA binaries.
  - Chain Hugging Face cache purging (rm -rf /root/.cache/huggingface) directly within the model-baking layer execution block to minimize disk image footprints and VM I/O thrashing.
- [ ] Evaluate migration from PyTorch to ONNX Runtime + NumPy (Post-Demo Phase)
  - Export SBERT (all-MiniLM-L6-v2) to ONNX format to drastically reduce initialization overhead.
  - Convert runtime vector operations (player vs. correct answer similarity matrices) from PyTorch tensor calls to native NumPy dot products and vector norms, permitting the total removal of the torch dependency from the container environment.

---

## 5. Gameplay / UX
- [ ] Improve MCQ rendering format consistency
- [ ] Refine evaluation disclaimer readability
- [ ] Add clearer chance-loss feedback UX

---

## 6. Evaluation System
- [ ] Tune EX semantic threshold boundary (0.3–0.5 zone) -> Review edge-case semantic failures
- [ ] Review AI judge escalation rules
- [ ] Validate MCQ semantic failure cases

---

## 7. Deferred / Exploration
- [ ] Consider streaming evaluation via FastAPI WebSocket

---

## 8. Generation Pipeline (Phase 2)

### Open decisions
- [ ] **Prompt + strategy versioning mechanism** — **Prompt + strategy versioning — which marker is authoritative.** `prompt_id` is now the version recorded in receipts and stamped on every record (commit c92b617), replacing the prompt filename.

  The remaining question is which should be the single source of truth: `prompt_id` or the filename. The safer approach is to make `prompt_id` authoritative and derive the filename from it. That way, a mismatch fails immediately when the code loads, rather than silently changing the version recorded in receipts.

  The downside is that this would require renaming the existing prompt files, and the notebooks currently reference those paths directly. Make this change the next time the notebooks are updated.
  
  `generation_strategy_version` still has no mechanism. Likely warrants an ADR.

- [ ] **Category vs. answer type — two different dimensions in one field.** `llm_predicted_category` currently mixes two different things: the **content category** (e.g. "Character Detail") and the **answer type** (e.g. "Number/Year"). These can conflict. For example, a question with the answer `47` was labelled "Character Detail", leaving no indication that the answer is numeric. The proposed fix is to split them:

  * `answer_type` is derived from the answer itself. The Phase 1 EDA classifier already identifies text, numeric, date, and year answers.
  * `content_category` is predicted by the LLM, since determining the subject category requires judgment.

  This keeps the two dimensions separate: **one is derived, one is predicted**.

  The change would affect the schema, enrichment prompt, and possibly FR evaluator routing. The evaluator currently routes based on `question_type` and ignores category, which may be because the current category field is unreliable. Resolve this during prompt testing.
- [ ] **ADR-P2-024 second nested field** — a further nested field in the enrichment/validation schemas is suspected to benefit from flattening; not yet identified. ADR left open to accumulate instances.
- [ ] **`PipelineMetadata` required-vs-Optional ordering** — `lex_enrich_prompt_version` and `semantic_enrich_prompt_version` are required but only knowable post-enrichment; `generation_prompt_version` is Optional but knowable at generation. Backwards relative to pipeline sequence. Confirms why DraftQuestion needs all-Optional.

### Validation gaps (enrichment fields)
- [ ] **Carry the tracer's enrichment audit into `qa_validation`** — the LLM Judge pass on hints, explanations and answer variations exists as tracer notebook work (§ 3.4) and does not run on pipeline output, so pipeline-generated hints have had no audit. See notebook § 3.4.1 for the three failure modes and what catches each.
- [ ] **Spoiler check** — string containment of `answer` / `answer_variations` in any hint. Cheap, unconditional, and the failure a player notices first.
- [ ] **About-ness check** — SBERT similarity floor between each hint and its question. SBERT already runs in `qa_validation`. Catches hints generated about the wrong question within a correctly id-matched batch — a mode that scales with batch size and that `syn_id` reconciliation cannot see. Threshold needs calibrating against a real batch before it enforces anything.
- [ ] **Prompt constraint (lex enrichment)** — hints describe the answer's role in the scene and do not assert verifiable properties of it. Removes the false-claim category rather than detecting it; the LLM judge is a coherence verifier, not an arithmetic one, and would pass a false numeric claim.
- [ ] **Numeric-claim check depends on `answer_type`** — only meaningful where the answer is a number, so it is gated by the taxonomy split above.

### Artifact storage
- [ ] **Directory layout** — move to per-run folder for operational artifacts: `07_pipeline_logs/runs/{run_id}/` holding manifest, log, receipt. Generated questions stay in `08_generated/` (data vs. metadata have different lifecycles; logs may be pruned, data is consumed downstream).
- [X] **Job-level log** one row per API call: `job_id`, `batch_id`, `run_id` model, versions, token breakdown, `finish_reason`, hyperparameters, timestamp, question count. Delivered as `{run_id}_{llm_pass}_calls.jsonl` (commits 7–8), with `GenerationCallEntry` / `EnrichmentCallEntry` in `core/telemetry.py` as the shapes. Per-pass rather than one appended file at top level, since `llm_pass` in the filename is what stops one pass overwriting another. The receipt derives its totals from this file at write time, so the two levels cannot disagree.
- [ ] **Run-level delta report** — reconcile planned (manifest) against produced (questions jsonl) against accounted (calls jsonl). The receipt's record counts are a breakdown, not a check: `records_rejected` is derived as the remainder, so the identity cannot disagree with itself. Comparing against what actually reached disk is the only check that can fail.      

### Code TODOs
- [ ] **Migrate pipeline LLM calls to google-genai** — `generate_questions.py` (rebuild the 503-only retry policy without `google.api_core.retry`) and `probe_api.py` (redesign around the new retry approach). Ideally on the shared LLM core (see §3). Unblocks removing `google-generativeai` (§9)
- [ ] **Cross-strategy pacing gap** — rate-limit delay only paces within a strategy (`i` resets per question type), so the first job of each strategy fires immediately after the previous strategy's last call. Limits are per-key across all calls: loop position ≠ time since last call. Proper fix: elapsed-time pacing at every call site. Low priority at 10 RPM. (TODO also in `generate_questions.py`)
- [X] Rename `fr_master_prompt._v0.2.txt` — stray dot before `_v0.2`
- [ ] **Enrichment writes no log file** — only generation calls `configure_file_logging`, so enrichment's Prefect output reaches the UI and terminal but nothing on disk. Belongs to the orchestrator, which should set logging up once for all three passes, same as the manifest.
- [ ] **Enrichment writes no manifest** — generation does. An enrichment pass's plan is the previous pass's receipt, so there is nothing new for a per-pass manifest to declare; one run-level manifest covering all three passes is the orchestrator's job. `save_run_manifest` would also currently crash on an enrichment strategy — it pops `json_response_schema` by name, and enrichment configs carry `input_dto` / `output_dto`, which are classes and not JSON-serializable.
- [ ] **`retrive_dto_from_jsonl_file` is only called with a hardcoded path** and builds `DraftQuestion` only, so it reads generation output and cannot reload a later pass's checkpoint. Both block `--resume`.
- [ ] Rename `retrive_dto_from_jsonl_file` → `retrieve_...` (typo)

### Verification debt
- [ ] **pytest for the telemetry models and failure branches** — the three enrichment failure branches (`transport_failure`, `no_candidates`, `response_unparseable`) have never executed against a live failure. Needs a fake response object whose `.text` property *raises* when there are no parts, mirroring the SDK — a fake returning `""` would let the original bug back in without the test noticing. Also: `CallEntry` validators, and the `save_run_completion` accounting against a fabricated calls file (no API calls needed for either).
- [ ] **Generation failure branches** — a raised call currently `continue`s and records nothing, so its tokens go unaccounted and no quarantine entry exists. Blocked calls are recorded but not labelled with a `failure_mode`, so they don't count toward batch loss. The parallel of commit b47d50b, and the thing worth closing before a book run.

## 9. Dependencies & Security
 
### Done (Oct 2026)
- [X] Runtime LLM service migrated to `google-genai` (PR #10); runtime `requirements.txt` switched (`google-genai==2.30.1`, `pydantic==2.14.1`)
- [X] Dependabot: urllib3 2.8.0, dulwich 1.2.9, tornado 6.5.9, Mako 1.4.2 (#294), hydra-core, apprise 1.11.0 (#298)
### Open
- [ ] **Remove `google-generativeai`** — blocked until the offline pipeline (§8) and the tracer lab / research notebooks (§11) are migrated or marked legacy. Its `protobuf<6` cap blocks:
  - [ ] datasets 5.0.1 (#292), fsspec / gcsfs 2026.6.0 (#293) — risk assessed as low (dev-only; `ReferenceFileSystem` unused; one trusted Hub dataset); tracked in a GitHub issue
  - [ ] Revisit the `protobuf==5.29.6` pin in runtime `requirements.txt` once dev is on protobuf 6
- [ ] **Next main-based image:** torch 2.13.0 security pin (in main's Dockerfile) and transformers 5.10.0 (main's `requirements.txt`) — not in the current deployed image; verify SBERT parity before shipping
- [ ] Lockfile for dev and runtime requirements (`.in` + pip-compile / uv) — `pip freeze` captures venv drift; runtime transitive deps are unpinned
- [ ] Align Python minor version between dev venv (3.12) and runtime image (3.11)
- [ ] Orphans in `requirements-dev.txt`: h2, aiohttp-retry, nltk, hf_transfer
- [ ] Dockerfile: drop obsolete `HF_HUB_ENABLE_HF_TRANSFER=1` from the model-download step; simplify `pip install torch torch==X` to `torch==X`
- [ ] Legacy headers on `docs/archive/` and `scripts/research/` files still importing the old SDK
---


## 10. Deployment
 
### Done (Oct 2026)
- [X] Deployed `sve:tracer-genai-20261017` — minimal-change hotfix on the existing tracer code (google-genai `llm_service`, requirements swap, `types.py` → `game_types.py`); smoke-tested locally and on the VM
- [X] Fixed latent `game_app/types.py` stdlib shadowing (exposed when the old SDK's startup side effect was removed)
- [X] Added `deploy/` record: `DEPLOYMENTS.md`, per-image freeze files, history backfilled (Phase 1, original tracer, dep-updates-ux); code snapshot archived in `data/10_backups` (DVC)
### Open
- [ ] **Validate main in a container build** — main's changes since the tracer (game_app refactor, observability, `core/models.py`) fail at startup against the production parquet; needs validation before the next main-based image
- [ ] Replace temporary `phase2_tracer_deploy/` staging with a direct build from `src/` + `requirements.txt` once phase 2 settles (staging drifted: `core`, Dockerfile torch pin)
  - Until then: sync the Dockerfile into staging along with `src/` and `requirements.txt`
- [ ] Add `.dockerignore`: `*.egg-info`, `__pycache__`, `mvp_phase1`, `notebook_support`
- [ ] VM cleanup once the new image is proven: `docker rm sve-runtime`, `docker rmi semantic-verification-engine:latest`
- [ ] Consider `--restart unless-stopped` for the runtime container
- [ ] Standing practice: tag images with commit hash + OCI revision label; one `DEPLOYMENTS.md` entry + freeze file per deploy
---
 
## 11. Notebooks & Research
- [ ] **Tracer lab overhaul** (`tracer_nlp_lab_v0.py`) — far behind; update in one batch with the offline refactor, including the google-genai migration. Must be migrated or retired before `google-generativeai` is removed
- [ ] **Runtime demo notebook** (`00_runtime_evaluation_walkthrough`) — tightly coupled to the lab; delink (warmup + judge → `llm_service`, drop the gRPC cleanup cell) in the same batch
- [ ] Other research notebooks on the old SDK — update only if needed, judged at the time (tracer demo partly supersedes them); otherwise mark legacy
