#  Execution Plan: SVE Sprints 

## Phase 1: The MVP** (Legacy)
  *Status: Completed*
  *Focus: Rules-based logic, CLI-MVP with baseline v.0 dataset, standalone container.*

---

## Phase 2: System + Intelligence
**Demo-First, Learning-Driven Execution**
*Status: Current*

This sprint plan is structured to **prove architectural viability first**, then extend capability, and only then invest in deeper internal polish where learning return is highest.

Key principles:
- Tracer bullets before polish
- Demos as validation artifacts
- Learning ROI over completeness
- CLI runtime retained intentionally
- Infrastructure changes only when justified

---

# 🔹 Phase 2 — Semantic Verification Demo (Tracer Bullet MVP)
## Phase Goal
> Deliver a playable Phase-2 demo that proves semantic answer validation works end-to-end and overcomes Phase-1 limitations using a minimal, controlled dataset.

This phase answers:
**“Does the semantic verification architecture work at all?”**

## Workflow 

Plan phase 2 sprints → Filter legacy → Normalize schema → Enrich & embed  → Generate synthetic → Validate separately  
→ Assemble Gold → Add context → Tiered validation → Release demo

## Sprint 2.0 — Phase-2 Scope Freeze & Demo Definition
**Sprint Type:** Planning / Guardrails

### Objective
Lock the smallest viable slice required to demonstrate Phase-2 semantic intelligence and prevent scope creep.

### Decisions to Freeze
- One dataset slice
- One SBERT model (off-the-shelf)
- One similarity strategy per question type
- CLI runtime retained
- Existing VM / container retained

### Explicitly Out of Scope
- Performance optimization
- Pipeline generalization
- Monitoring / agents
- Runtime refactor (FastAPI)
- UX polish

### Success Criteria
There is zero ambiguity about:
- what is being demoed
- what is intentionally ignored

---

## Sprint 2.1 — Legacy → Gold v0 (Foundational)

## Sprint Goal
Prove that legacy data can be normalized into a truthful Phase-2 contract with shared reasoning scaffolding and type-aware validation.

## Task Group — Legacy Dataset Preparation

### 2.1.1 Filter out Yes/No (YN) questions and define standard schema [Done]
**Description:**  
- Create defined schema for datasets going forward with specified data types.
- Remove YN questions from legacy data prior to Phase-2 processing.
- Strip legacy dataset to match BaseQuestion schema (with out LLM enrichment features -> hint_1, explanation and the optional fields). These will be added in the tracer by the Context Refinery.

**Acceptance Criteria:**
- All YN questions excluded
- Remaining types: FR, EX, MCQ
- Removal count logged
- Aligned with ADR-P2-019
- standard Pyndantic schema for MCQ, EX, FR questions
- Legacy dataset ready for enrichment with LLM prompting

### 2.1.2 Update generation / enrichment prompt (schema-first) [Done]
**Description:**  
Upgrade the master prompts so both legacy and synthetic questions emit Phase-2 instructional scaffolding.

**Scope:**
- Freeze schemas per question type
- Add to all prompts:
  - `hint_1` — light nudge (directional) **[required]**
  - `hint_2` — stronger cue (key concept) **[optional]**
  - `hint_3` — near-solution framing **[optional]**
  - `explanation` — full reasoning **[required]**
- Legacy run only:
  - Generate `answer_variations` based on existing question + answer text **[required for FR / EX only]**


**Validation policy**
- Absence of these fields implicitly indicates unverified or unavailable source grounding.
- No attempt is made to backfill sources in Phase 2.

This policy ensures:
- schema consistency
- semantic readiness
- zero silent data corruption

**Acceptance Criteria:**
- Generated records conform to defined schemas
- No additional enrichment logic added
- Prompt updated once (no tuning loop)

### 2.1.3 Normalize legacy data to Phase-2 schemas [Done]
**Description:**  
The question type (FR / EX / MCQ) is determined prior to enrichment and governs which fields are generated.
Use LLM to **enrich legacy questions without modifying their wording** by filling in missing Phase-2 fields derived strictly from the existing question and correct answer. The LLM generates reasoning scaffolding (`hint_1`, optional `hint_2` / `hint_3`), answer variations, and a high-level conceptual explanation. The LLM must not add new facts, rewrite the question, or fabricate source grounding; explanations must remain conceptual and source-agnostic. Fields that cannot be inferred safely are left empty.

- prevent cross contamination across hints and explanations with negative constraint to prompt: e.g. *"Hints must provide directional guidance without using the keywords found in the `answer` or `answer_variations` fields."*

**Schema mapping:**
- FR / EX → `StandardQuestion`
- MCQ → `MCQQuestion`

#### Required fields (legacy FR / EX)
- `question`
- `answer`
- `answer_variations`
- `hint_1`
- `explanation`

#### Required fields (legacy MCQ)
- `question`
- `options[]` (structured list)
- exactly one correct option
- `hint_1`
- `explanation`

#### Optional fields (legacy, all types)
- `hint_2`
- `hint_3`
- `source_quote`
- `source_reference`

> Absence of source fields implicitly indicates unverified grounding.  
> No attempt is made to hallucinate or backfill sources in Phase 2.

**Acceptance Criteria:**
- ≥95% of legacy FR / EX records pass Pydantic validation
- MCQs meet structural validity or are dropped
- Invalid records dropped (no repair loops)

### 2.1.4 Generate embeddings & validate (legacy) 
[Postponed to after synthetic gen and to be done with qa_validation pipeline logic]
**Description:**  
Generate SBERT embeddings required for **offline deduplication** and **runtime semantic validation**, with clearly separated responsibilities.

#### Embedding policy

**For semantic deduplication (offline only):**
- All question types (FR, EX, MCQ):
  - Question text embeddings are generated and used exclusively for deduplication.
  - Question embeddings are **not** used for runtime answer validation.

**For runtime semantic validation:** generate in batches
- FR / EX:
  - Embeddings generated for:
    - correct answer
    - all answer variations
- MCQ:
  - Embeddings generated for all option texts (correct + distractors)

#### Acceptance Criteria
- Question embeddings exist for all records and are usable for deduplication
- All required answer / option embeddings exist (no nulls)
- All records pass type-specific Pydantic validation
- Embeddings loadable by runtime (answer / option only)

### Publishing
- Publish **Gold v0** (legacy only)
- Version artifacts (DVC)

## Sprint 2.1 Exit Criteria (Non-Negotiable)
Sprint 2.1 is **DONE** when:

- ✅ Gold v0 exists (legacy only)
- ✅ FR / EX records include answer variations, hints, explanation, and embeddings
- ✅ MCQs include structured options with option embeddings
- ✅ Optional fields do not block validation
- ✅ Prompt is reusable for synthetic generation
- ✅ Dataset loads cleanly via runtime loader

> *This sprint proves data integrity and shared reasoning scaffolding — not intelligence.*

---

# Sprint 2.2 — Synthetic Generation → Gold v1 (Expansion)

## Sprint Goal
Demonstrate that the Content Factory can extend Gold safely without fragmenting schemas.

### 2.2.1 Generate synthetic questions

**Scope:**
- 1 book
- ~5 chapters (sequential)
- Use the same upgraded prompt
- Generate:
  - FR: ~5–6 / chapter
  - EX: ~5–6 / chapter
  - MCQ: ~5–6 / chapter (structured options)

**Acceptance Criteria:**
- Grounded in source text
- Non-trivial
- FR / EX have meaningful answer variations

### 2.2.2 Validate synthetic questions

**Scope:**
- Remove semantic duplicates (within batch and vs Gold v0)
- Generate required embeddings
- Enforce strict schema validation
- MCQ distractor collision audit:
  - For all MCQs, calculate the pairwise cosine similarity of all options.
  - Constraint: If $\Delta = Sim(Option_i, Option_j) > \text{Collision\_Threshold}$, the record fails validation -> question rejected.
  - Goal: Ensure the "Semantic Gap" between distractors is wide enough to avoid runtime ambiguity.  

**Acceptance Criteria:**
- ≥95% pass Pydantic validation
- Failed records dropped (no manual fixes)
- No schema divergence
- Dataset loads cleanly

### 2.2.3 Publish Gold v1

**Acceptance Criteria:**
- Gold v1 contains legacy + synthetic
- Synthetic records tagged via metadata
- Identical schemas across sources

### Exit Criteria (Non-Negotiable)

Sprint 2.2 is **DONE** when:
- Gold v1 exists (legacy + synthetic)
- Hint and explanation schema is identical across sources
- Synthetic records are distinguishable via metadata
- Dataset still loads cleanly via runtime loader

> *This sprint proves extensibility — not semantic reasoning.*
---

# 🟣 Sprint 2.3 — Context + Tiered Answer Checking (Intelligence) + deploy

## Sprint Goal
Make semantic intelligence visible and undeniable in gameplay.

### Tiered answer validation
**Description:** 
Implement validation tiers per question type.

**FR / EX**: Exact → Fuzzy → Semantic (answer + variations)
**MCQ**: Exact → Fuzzy → Constrained semantic (option embeddings only)

**MCQ semantic rules:**
- Compare player input embedding to option embeddings only
- Accept only if:
  - similarity ≥ τ_mcq
  - best similarity exceeds second-best by margin Δ
  - check for semantic collision between options: tie-breaker policy if two distractors are semantically similar (e.g. Regulas Black, Sirius Black) -> reject question in qa_validation stage.
  - resolved option is correct

### Rebuild runtime container
**Acceptance Criteria:**
- Container builds successfully
- No infra refactor

### Deploy demo
**Acceptance Criteria:**
- CLI demo runs end-to-end
- Gold v1 loads correctly
- Semantic improvement is visible in gameplay

---

## Sprint 2.3 Exit Criteria

- Phase-1 failure succeeds via semantic logic
- MCQs accept shorthand inputs (e.g. “sirius”)
- Ambiguous MCQ inputs rejected
- Logs show which tier accepted the answer
- Demo playable end-to-end

---

# Phase-2 MVP Exit Criteria

Phase 2 is **DONE** when:
- Gold dataset exists (legacy + synthetic)
- FR / EX semantic answers accepted correctly
- MCQs tolerate typos and partial input
- Phase-1 limitation is demonstrably resolved
- Demo is playable without explanation

---

# 🔹 Phase 3 — Runtime Intelligence Demo (MVP)

## Phase Goal
> Demonstrate that the architecture extends cleanly to support runtime intelligence without rewriting Phase-2 foundations.

This phase answers:
**“Does the design scale conceptually?”**

## Sprint 3.0 — Phase-3 Scope & Guardrails
<!-- **Duration:** 1–2 days -->

### Objective
Define Phase-3 strictly as a **capability addition**, not a system rewrite.

### Decisions to Freeze
- CLI runtime retained
- Same Gold dataset
- Same embeddings
- Same VM / SSR deployment

### Explicitly Out of Scope
- Production hardening
- Monitoring agents
- Scale optimizations
- FastAPI refactor

---

## Sprint 3.1 — Lightweight Runtime Intelligence (Demo)
<!-- **Duration:** 4–6 days  -->
**Sprint Type:** Capability Expansion

### Objective
Introduce a new intelligence layer that qualitatively changes gameplay.

### Scope (one of the following)
- Persona layer
- Lightweight judge for ambiguous answers
- Explanation layer

### Constraints
- No refactor of Content Factory
- No refactor of Context Refinery
- Minimal logic only

### Success Criteria
A player experiences a clear qualitative difference in gameplay driven by runtime intelligence.

---

## Sprint 3.2 — Phase-3 Demo Closure

### Deliverables
- Phase-3 MVP ADR
- README update:
  - What Phase-3 adds
  - Why the architecture enabled it
- Explicit “What Phase-3 proves” section

---

# 🔹 4: Phase 2 Polish (Post-Validation, Learning-Driven)
This phase is entered **only after Phase-3 demo exists**.

## Sprint 4.1 — Context Refinery Deep Dive (Primary DS / NLP Work)
**Duration:** Open-ended, paced  
**Sprint Type:** Data Science / Enrichment

### Objective
Deepen semantic enrichment quality where learning value is highest.

### Focus Areas
- Feature engineering
- Semantic signal quality
- Evaluation metrics
- Schema discipline
- Toward Feature Store formalization

**Notes**: This is the main **data science & NLP learning phase**.

### 4.1.1 NER Integration
**Description:** 
Named Entity Recognition (NER) work is intentionally deferred to this phase -> after MVP developement.
Implement NER to extract character names, locations, and magical objects to create a "Semantic Weighting" system (e.g., giving more importance to the 'Entity' than the 'Adjective' during answer validation).

### Focus Areas
- **NER Feature Engineering**: Leveraging spaCy or Transformers to tag Gold entities.
- **Semantic signal quality**: Tuning similarity thresholds based on entity presence. If two MCQ options share a Named Entity (e.g., both mention "Black"), the Refinery should flag it for a "disambiguation prompt" or a distractor rewrite.
- **Toward Feature Store formalization**: Mapping NER tags to the Context Refinery schema.

### 4.1.2 semantic threshold calibration & SLM alignment
- fine-tune sbert model
- For FR/ EX: calibrate sbert score thresholds for ambiguous score range for answer checking (cosine similarity (tau) upper and lower bounds) with handoff to the SLM judge. 
 
- fine tune SLM judge role and feedback.

### 4.1.3 - The Hallucination Guard for MCQ
Filter the Gold dataset for semantic "Near-Misses" and factual consistency.
- **Method A (Semantic Similarity)**: Calculate the SBERT distance between the answer and each of the 3 distractors. If a distractor is too similar (e.g., > 0.95), flag it for manual review—it's either a hallucinated typo or a "trick" question that's too confusing for the player. Can allow for *tricky* MCQ: allow lower $\Delta$ margin between options (instead of rejecting as done in phase 2). Flag these questions in `qa_validation` pipeline that they require SLM intervention if the player provides ambiguous answer.
- **Method B (Entity Consistency)**: Use NER model to check if the answer and options share the same label (e.g., if the answer is a PERSON, all options should be PERSON).


## Sprint 4.2 — Content Factory Refinement (Optional)

**Duration:** Optional  
**Sprint Type:** Upstream Quality

### Objective
Refine upstream generation only if demanded by Context Refinery improvements.

### Examples
- Prompt robustness
- QA logic
- Sampling strategies
- Data quality scoring

---

# Strategic Decisions

| Decision | Rationale |
|--------|-----------|
| CLI runtime retained | UX is not the core risk |
| VM / SSR retained | Minimize refactor tax |
| FastAPI deferred | Only justified by scale/time |
| Demo before polish | Architecture must earn optimization |
| DS polish postponed | Needs downstream demand |

---
