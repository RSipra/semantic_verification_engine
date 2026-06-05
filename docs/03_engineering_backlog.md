
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
- [ ] Separate evaluation engine into standalone service boundary
- [ ] Introduce event-based controller logging (optional future refactor)

---

## 4. Performance
- [ ] SBERT cold start benchmarking
- [ ] LLM warmup latency measurement in container
- [ ] Evaluate caching strategy for repeated embeddings

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