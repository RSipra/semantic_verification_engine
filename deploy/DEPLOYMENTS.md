# Deployments

Record of container images deployed to the VM. One entry per deploy.
Freeze files (`freezes/`) list each image's installed packages, with the Python
version on the first line. Files are named after the image tag.

---

## 2026-10-17: sve:tracer-genai-20261017

**Type:** Minimal-change hotfix on the existing tracer code (not latest main)

**Baseline:** deployed tracer code from the VM (`3e1bc6f7` + uncommitted changes to
`core/embeddings.py`, `engine/startup.py`, `game_app/metrics_aggregator.py`)

**Changes on top of the baseline (only these):**
- `engine/services/llm_service.py` replaced with the google-genai version (from main)
- `requirements.txt`: `google-generativeai` → `google-genai==2.30.1`; `pydantic` → 2.14.1
- `game_app/types.py` → `game_types.py` (stdlib shadowing, exposed by the SDK swap)

**Why not main:** main's changes since the tracer have not yet been validated
in a container build. Deployed as a minimal change on the tracer instead.

**Not included (still pending, on main):**
- torch 2.13.0 security pin (main's Dockerfile; image still runs torch 2.10.0+cpu)
- transformers 5.10.0 (main's requirements.txt)
- game_app refactor + observability commits since the tracer

**Packages:** old Gemini SDK + gRPC stack removed; google-genai + deps added;
transitive drift from unpinned deps (incl. urllib3 2.8.0 fix); Python 3.11.15 → 3.11.17

**Artifacts:**
- Freeze: `freezes/freeze_sve_tracer-genai-20261017.txt`
- Code snapshot: `snapshots/src_sve_tracer-genai-20261017.tar.gz`

**Replaces:** `sve:dep-updates-ux` (container `sve-latest`, kept for rollback)

**Smoke test (local):** startup OK; LLM judge call OK on primary model
**Smoke test (VM):**played a full round via the external link; LLM judge call OK
(`google-genai` 2.30.1 confirmed in container; `google-generativeai` absent);
session saved to `game_data` volume

**Container:** `sve-tracer-genai` (port 8080, `--env-file config.env`,
`TERM=xterm-256color`, volume `/home/reema_iqbal/game_data:/app/runtime`, no restart policy)
**Rollback:** `docker stop sve-tracer-genai && docker start sve-latest`

- Code snapshot: `data/10_backups/src_sve_tracer-genai-20261017.tar.gz` (DVC; src, requirements.txt, Dockerfile)
---


## ~2026-07: sve:dep-updates-ux
Dependency updates + UX changes. Container: sve-latest.
Freeze: freezes/freeze_sve_dep-updates-ux.txt

## ~2026-06: semantic-verification-engine:latest
Original Phase 2 tracer image. Container: sve-runtime (stopped).
Freeze: freezes/freeze_semantic-verification-engine_latest.txt

## Phase 1 (legacy)
Exact-match game; image archived as tar on DVC (<path>).
Freeze: freezes/freeze_<phase1>.txt (if captured)