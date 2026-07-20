
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
- [X ] SBERT cold start benchmarking
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
- [ ] **Prompt + strategy versioning mechanism** — blocks `generation_prompt_version`and `generation_strategy_version` fields on the record. Currently only a filename (`fr_master_prompt._v0.2.txt`); no registry or archive. Options: manual version constants in config (git as archive), content hash (self-verifying), or both. Same mechanism should cover prompts and strategy config. Likely warrants an ADR.
- [ ] **ADR-P2-024 second nested field** — a further nested field in the enrichment/validation schemas is suspected to benefit from flattening; not yet identified. ADR left open to accumulate instances.
- [ ] **`PipelineMetadata` required-vs-Optional ordering** — `lex_enrich_prompt_version` and `semantic_enrich_prompt_version` are required but only knowable post-enrichment; `generation_prompt_version` is Optional but knowable at generation. Backwards relative to pipeline sequence. Confirms why DraftQuestion needs all-Optional.

### Artifact storage
- [ ] **Directory layout** — move to per-run folder for operational artifacts: `07_pipeline_logs/runs/{run_id}/` holding manifest, log, receipt. Generated questions stay in `08_generated/` (data vs. metadata have different lifecycles; logs may be pruned, data is consumed downstream).
- [ ] **Job-level log** (new feature, deferred) — one row per API call: `job_id`, `batch_id`, `run_id`, model, versions, token breakdown, `finish_reason`, hyperparameters, timestamp, question count. Fills the missing middle grain between manifest/receipt (run-level) and JSONL (question-level). Enables cost/drift analysis at correct granularity — job-level token counts on question rows would be denormalized and easy to misuse. Data already computed in `parse_and_save`. If added: single appended CSV at top level, not per-run files (avoids globbing and the append-to-Parquet problem). Skip a separate runs index — most run metrics are derivable by aggregating jobs, and the receipt JSON covers per-run human reading.

### Code TODOs
- [ ] **Cross-strategy pacing gap** — rate-limit delay only paces within a strategy (`i` resets per question type), so the first job of each strategy fires immediately after the previous strategy's last call. Limits are per-key across all calls: loop position ≠ time since last call. Proper fix: elapsed-time pacing at every call site. Low priority at 10 RPM. (TODO also in `generate_questions.py`)
- [ ] Rename `fr_master_prompt._v0.2.txt` — stray dot before `_v0.2`