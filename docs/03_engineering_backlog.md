
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
- [ ] SBERT cold start benchmarking
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