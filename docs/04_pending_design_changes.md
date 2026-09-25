# Pending Design Changes

Design decisions made but not yet reflected in the code, the design doc, or an
ADR. This is a staging area, not a second source of truth: **an entry is deleted
from here once it lands in an ADR and the code.** If an entry has been sitting
here for more than a phase, it was either not a decision or not a priority —
resolve it either way.

Each entry records the reasoning, not just the conclusion. The reasoning is the
expensive part to reconstruct.

| # | Change | Status |
|---|---|---|
| 1 | File-first handoff between pipeline stages | Decided |
| 2 | Structural gate moves to the producer | Decided |
| 3 | Receipt readers must tolerate schema drift | Decided |

---

## 1 · File-first handoff between pipeline stages

**Status:** Decided, not implemented
**Date:** 2026-09-24

### The change

Files become the default handoff between stages. Carrying DTOs in memory becomes
an explicit opt-in "fast" mode, set as a run intent on the orchestrator rather
than per module.

### Why

Today the fast path is the default and the durable path is a manual fallback
nothing calls. Checkpoints are written on every batch, but no code reads them
back on a failure — `retrive_dto_from_jsonl_file` exists and is only called with
a hardcoded test path. So a run that dies partway must restart from scratch, and
the cost of that is what made enforcing the quarantine thresholds unattractive.

Inverting the default makes the safe behaviour automatic and the shortcut
deliberate. That is the right way round for an option that trades correctness
for speed.

### Constraints

- **Writes always happen.** Fast mode changes what the next stage *reads*, never
  whether the artifact exists. A fast run that left no trace would have shortcut
  its way out of traceability.
- **Fast mode skips the round-trip, not the gate.** DTOs are constructed through
  the same models either way, so the schema check has effectively run. What is
  lost is the serialisation check — whether the data survives Parquet. That is a
  real check (it is how the `np.ndarray` coercion problem surfaced) but a
  different one, and the distinction should be stated wherever the mode is
  documented.
- **Within one process, in-memory is correct.** The DTO chain
  (`DraftQuestion` → `LexDraftQuestion` → `SyntheticStandard`) is a same-process
  handoff and should stay in memory. The rule applies at process boundaries,
  where nothing carries memory across.

### Pairs with: resume

The two solve the same problem from opposite ends, and enforcing abort
thresholds only becomes affordable once a resume exists.

A resume needs:
- A loader that finds a run's checkpoints and rebuilds DTOs
- Filtering already-completed records out of the input
- An explicit `--resume <run_id>` flag, so a normal run never picks up stale state

**Open question:** `batch_id` and `job_id` use `short_uuid()`, which regenerates
on every run. `syn_id` is built from them, so a resumed run produces different
ids for the same content — id-based filtering may not work across a resume
without changing how those ids are minted.

### Considered and rejected

Prefect's built-in result persistence. It would give resume with less code, but
it stores framework-shaped state in Prefect's own layout rather than the
inspectable artifacts this design depends on.

### Actions

- [ ] **Write ADR-P2-020 — file-first handoff, fast mode as opt-in.** Record the
      default inversion, the writes-always-happen constraint, and the
      round-trip-vs-gate distinction. Note Prefect result persistence as
      considered and rejected.
- [ ] **Write ADR-P2-021 — resume from checkpoints.** Depends on resolving the
      `short_uuid()` question first; an id scheme that does not survive a resume
      makes the ADR unwritable.
- [ ] **Update design doc** — data lifecycle section: state that files are the
      handoff between stages and in-memory is an opt-in mode. Add run modes to
      the execution notes.
- [ ] **Code — orchestrator (new module):** holds the run-intent mode
      (`standard` / `fast`) and sequences the stages.
- [ ] **Code — `enrich_questions.py`:** resume loader, filter completed records,
      `--resume <run_id>` flag.
- [ ] **Code — `generate_questions.py`:** same resume path; decide whether
      `short_uuid()` stays in `batch_id` / `job_id`.
- [ ] **Code — shared utilities:** one loader per tier owning the known Parquet
      coercions (the `np.ndarray` validator is the template), so the rules live
      in one place rather than being rediscovered per call site.

---

## 2 · Structural gate moves to the producer

**Status:** Decided, not implemented
**Date:** 2026-09-24

### The change

The Bronze structural Pydantic gate runs at the **end** of the
generation/enrichment pipeline, not at the **entry** to the validation pipeline.

Silver is unchanged: still materialized inside `qa_validation`, still owns
embeddings and `master_id`, still the system of record. Gold remains a derived,
schema-gated projection of Silver — not a mirror. Only the structural gate moves.

### Why

- **The producer can diagnose; the consumer cannot.** When construction fails at
  the end of enrichment, the raw LLM response, source DTO, batch and prompt
  version are all in scope, and a quarantine mechanism already exists to catch
  it. Downstream, validation would see a malformed row with no idea which call
  produced it.
- **Cost.** A record that cannot pass Bronze has already consumed enrichment
  tokens. Catching it at validation's entry means it also travelled through
  staging. Same shift-left reasoning as the unsupported-question-type guard that
  fires before any API call.
- **One enforcement point.** Enrichment already constructs DTOs through these
  models, so a gate at validation's entry enforces the same schema a second time
  in a different module.

### Consequence

Validation then **trusts** Bronze rather than verifying it. So any route into
Bronze must run the same gate — this needs stating as an invariant, not left
implicit. The legacy preprocessing path is exactly such a route.

### Actions

- [ ] **Amend ADR-P2-011** (Validation Layer / Pydantic) — it currently places
      schema enforcement at the Silver layer entrance. Either revise it or
      supersede it with a new ADR; decide which when writing.
- [ ] **Update design doc — Phase 2 Architectural Invariants:** add "every route
      into Bronze runs the structural gate" as an explicit invariant, with the
      enforcing component named.
- [ ] **Update design doc — Figure 5** (Content Factory architecture): move the
      gate to the producer side.
- [ ] **Update design doc — P2 Data lifecycle table:** clarify that Bronze is
      the structurally gated handoff, and that Silver's own gate remains inside
      `qa_validation`.
- [ ] **Code — `enrich_questions.py`:** run the structural gate at the end of
      the semantic pass, before handoff; failures go to quarantine with the
      existing mechanism.
- [ ] **Code — validation pipeline (notebooks today):** remove the entry-side
      structural check once the producer-side gate is live; keep the semantic
      checks.
- [ ] **Code — legacy preprocessing script (not yet written):** must run the
      same gate, since validation will now trust Bronze.
- [ ] **Code — `core/models.py`:** no change expected; confirm the Bronze schema
      is the right class to gate on before implementing.

---

## 3 · Receipt readers must tolerate schema drift

**Status:** Decided, partially implemented
**Date:** 2026-09-24

### The change

Any code that reads run receipts must tolerate fields that did not exist when
older receipts were written. Read optional or later-added fields with `.get()`
and a sensible default; keep direct `[]` access only for fields present since
the format's first version.

### Why

Receipts are immutable history. Once written they are never migrated — that is
the point of keeping a run history, and regenerating them is impossible anyway
since a run cannot be replayed. So the set of receipts on disk will always span
several code versions, and a reader that assumes the current shape breaks on
anything older.

Found concretely: `create_run_report` raised `KeyError: 'quarantined'` reading a
receipt written one commit before that field was added.

### The rule, stated so it is not "tidied" away later

The choice between `[]` and `.get()` depends on the data's lifetime, not on
style:

- **Same run, same code version** — use `[]`. A missing key is a bug and should
  fail loudly. This is why `save_run_completion` reads call entries with `[]`:
  the entries were written moments earlier by the same code.
- **Across runs and code versions** — use `.get()` with a default. A missing key
  is expected history, not a bug.

Wherever a `.get()` exists for this reason, say so in a comment. Otherwise it
reads as inconsistency and someone will make it match its neighbours.

### Scope beyond the report

This applies to everything that reads accumulated receipts, including the two
report scopes that do not exist yet:

- Run-level delta (plan vs actual across passes)
- Run-over-run trend

Both read across runs spanning code versions by definition, so both inherit the
constraint.

### Open question

Whether to add a `schema_version` to the receipt. It would let a reader branch
explicitly rather than inferring shape from which keys are present, and would
make a future migration script possible. Against: it is another field to
maintain, and `.get()` handles additive changes without it. Revisit if a change
ever *removes* or *renames* a field rather than adding one — that is the case
`.get()` cannot absorb.

### Actions

- [ ] **Code — `create_run_report`:** use `.get()` for `quarantined`, with the
      comment explaining why. *(done in this commit)*
- [ ] **Code — future receipt readers:** apply the same rule; state it in the
      shared utilities module when the readers are extracted there.
- [ ] **Write ADR or fold into the receipt ADR** — this is a property of the
      artifact format, so it may belong in whichever ADR documents the receipt
      rather than standing alone.
- [ ] **Decide on `schema_version`** — see the open question above.
