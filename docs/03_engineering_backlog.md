
# Engineering Backlog

---

## 1. Testing
- [ ] Controller unit tests (turn lifecycle, scoring)
- [ ] Integration test: full game loop (mocked input)
- [ ] SessionReport serialization roundtrip test
- [ ] Edge case replay runner for evaluator regression

## 2. Observability
- [ ] Add main and controller lifecycle events
- [ ] Add latency metrics for evaluator tiers
- [ ] Add AI judge usage metrics
- [ ] Add session analytics reporting
- [ ] Add JSONL/structured persistence layer for SessionReport / SessionAggregates

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

---

## 4. Performance
- [X] SBERT cold start benchmarking
- [ ] LLM warmup latency measurement in container
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
- [ ] **Cross-strategy pacing gap** — rate-limit delay only paces within a strategy (`i` resets per question type), so the first job of each strategy fires immediately after the previous strategy's last call. Limits are per-key across all calls: loop position ≠ time since last call. Proper fix: elapsed-time pacing at every call site. Low priority at 10 RPM. (TODO also in `generate_questions.py`)
- [X] Rename `fr_master_prompt._v0.2.txt` — stray dot before `_v0.2`
- [ ] **Enrichment writes no log file** — only generation calls `configure_file_logging`, so enrichment's Prefect output reaches the UI and terminal but nothing on disk. Belongs to the orchestrator, which should set logging up once for all three passes, same as the manifest.
- [ ] **Enrichment writes no manifest** — generation does. An enrichment pass's plan is the previous pass's receipt, so there is nothing new for a per-pass manifest to declare; one run-level manifest covering all three passes is the orchestrator's job. `save_run_manifest` would also currently crash on an enrichment strategy — it pops `json_response_schema` by name, and enrichment configs carry `input_dto` / `output_dto`, which are classes and not JSON-serializable.
- [ ] **`retrive_dto_from_jsonl_file` is only called with a hardcoded path** and builds `DraftQuestion` only, so it reads generation output and cannot reload a later pass's checkpoint. Both block `--resume`.
- [ ] Rename `retrive_dto_from_jsonl_file` → `retrieve_...` (typo)

### Verification debt
- [ ] **pytest for the telemetry models and failure branches** — the three enrichment failure branches (`transport_failure`, `no_candidates`, `response_unparseable`) have never executed against a live failure. Needs a fake response object whose `.text` property *raises* when there are no parts, mirroring the SDK — a fake returning `""` would let the original bug back in without the test noticing. Also: `CallEntry` validators, and the `save_run_completion` accounting against a fabricated calls file (no API calls needed for either).
- [ ] **Generation failure branches** — a raised call currently `continue`s and records nothing, so its tokens go unaccounted and no quarantine entry exists. Blocked calls are recorded but not labelled with a `failure_mode`, so they don't count toward batch loss. The parallel of commit b47d50b, and the thing worth closing before a book run.
