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
| 4 | Orchestrator run modes, and what the manifest describes | Decided in principle |
| 5 | Provider portability — the LLM call seam | Open |
| 6 | What makes a dataset Production_Blue | Open |
| 7 | `chunk` and `batch` used interchangeably | Decided |

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

## 4 · Orchestrator run modes, and what the manifest describes

**Status:** Decided in principle, not implemented
**Date:** 2026-09-25

### The change

The orchestrator runs any contiguous subsequence of the three passes, not only
the full chain. It mints the run id, attaches file logging once, and writes one
manifest for the whole run rather than one per pass.

### Why three modes, not one

- **Full** — generation → lex → semantic. The normal synthetic path.
- **Generation only** — produce DraftQuestion DTOs and stop. This is how prompt
  quality gets checked before enrichment tokens are spent on bad questions.
- **Enrichment only** — take existing DTOs and enrich. This is the legacy
  bootstrap path and the resume path.

So a partial run is not a degenerate case; two of the three modes are how the
pipeline is actually used during development and for legacy content.

### What falls out

**Input when generation is skipped.** A file path read into DTOs via
`retrive_dto_from_jsonl_file` — the same door legacy preprocessing uses.

**Who mints the run id.** The orchestrator, not generation. Today generation
mints it and enrichment's `__main__` mints its own, so a chained run has to
thread one through. With an orchestrator, nothing else owns the id.

**File logging happens once.** `configure_file_logging` attaches a handler to
the process-wide "prefect" logger, so calling it per pass would attach several
and write every line once per handler. The caller — orchestrator or `__main__` —
calls it; flows never do. This follows the rule already applied to paths and
llm_pass: flows supply, helpers receive.

**The manifest describes the run, not the pass.** Generation's manifest records
books, chapters and strategies; an enrichment manifest would record DTO count,
question types, chunk size. Rather than a second manifest shape, the orchestrator
writes one plan for the run: which stages, what input, what settings. Plan once,
record per stage — receipts stay per pass.

### Open question

Whether enrichment run standalone still needs its own manifest and file log, or
whether standalone runs are always launched through the orchestrator. If the
latter, `__main__` in each pipeline stays a smoke-test entry point only.

### Actions

- [ ] **Code — orchestrator (new module):** mode selection, run id, file
      logging, run-level manifest, stage sequencing
- [ ] **Code — `generate_questions.py`:** stop minting the run id and calling
      `configure_file_logging` when invoked through the orchestrator
- [ ] **Code — `enrich_questions.py`:** accept an input file path for the
      enrichment-only mode
- [ ] **Code — `save_run_manifest`:** takes a pre-built plan dict rather than
      generation-shaped arguments
- [ ] **Update design doc** — execution section: document the three run modes
- [ ] **Write ADR** — or fold into the file-first handoff ADR (entry 1), since
      the orchestrator is what holds the run mode there too


## 5 · Provider portability — the LLM call seam

**Status:** Open — seam identified, approach not decided
**Date:** 2026-10-02

### The problem

The pipelines are coupled to one provider SDK. Substituting a provider today
means rewriting six functions, and there is no interface between them and the
rest of the pipeline.

The coupling is contained, though, and worth being precise about where it lives:

| Function | Coupled to |
|---|---|
| `configure_api` | `genai.configure(api_key=...)` |
| `make_api_call` | `GenerativeModel`, `GenerationConfig`, `generate_content`, `response_mime_type`, `request_options` / `api_retry.Retry` / `ServiceUnavailable` |
| `measure_template_tokens` | `model.count_tokens(...)` |
| `calculate_token_metrics` | `usage_metadata.*` field names |
| `check_safety_and_feedback` | `candidates[0].finish_reason.name`, `prompt_feedback` |
| `process_and_save_candidates` | `candidates`, `content.parts[0].text` |

Plus two reads in the enrichment flow (`response.candidates`, `response.text`)
and four config keys (`candidate_count`, `top_p`, `response_mime_type`).

### Why this is already solved more than it looks

`CallEntry` is the normalisation boundary. Everything downstream of it — the
receipt, the report, the thresholds, the trend views, the orchestrator — is
provider-agnostic, because it reads a model rather than an SDK response.

That is also the same seam the shared-utilities split identified: "call the
model" (coupled) versus "account for the call" (portable). Provider
portability is a second, independent reason the same boundary is the right one.
A boundary two unrelated forces agree on is usually real.

### The one leak past the seam

`tokens: dict` on `CallEntry` is untyped, so provider-shaped keys pass straight
through into the receipt and the report:

- `4_output_candidates` — "candidates" is Gemini vocabulary
- `6_thinking_actual` — not every provider reports reasoning tokens separately.
  Where it isn't reported, the correct value is `None` (not measured), not `0`
  (measured as zero) — the same distinction that matters for Flash-Lite today.
- `3_input_cached_actual` — maps to one field here, but caching elsewhere often
  splits into cache *read* and cache *write*, billed differently. One key
  cannot hold two numbers.

Fix when the time comes: give the token breakdown its own model in
`core/telemetry.py` with provider-neutral names and `None` meaning
not-reported.

### Why not now

An adapter designed with only one SDK in hand will be shaped like that SDK.
The honest way to find the interface is to port one call path to a second
provider as a throwaway experiment and see what refuses to fit.

Note that a Gemma judge via AI Studio would **not** test this — it goes through
the same `generativelanguage` surface.

### Not hypothetical

Phase 3 states a local-models requirement for regulated domains, and a Gemma
judge was floated for quota isolation between pipeline and runtime. This is a
deferred stated need, not speculation.

### Actions

- [ ] **Read `src/engine/services/llm_service.py` first.** It exists in the
      runtime and carries its own rate-limit assumption (10 RPM / 6s buffer).
      There may already be a second, divergent provider-calling implementation;
      designing the seam without reading it risks a third.
- [ ] **Experiment — port one call path to a second provider.** Throwaway, not
      a refactor. The goal is to find out what the interface needs, not to ship
      an adapter.
- [ ] **Code — `core/telemetry.py`:** typed token-breakdown model with
      provider-neutral field names; `None` for not-reported.
- [ ] **Write ADR** once the experiment says what the seam looks like. Not
      before — an ADR written now would record a guess.
- [ ] **Update design doc** — note the coupling and the seam in the
      orchestration section, so a reader knows it is known rather than missed.

---

## 6 · What makes a dataset Production_Blue

**Status:** Open — needs resolving before the first Blue is written
**Date:** 2026-10-02

### The question

Is Blue **declared** by the author, or **earned** against criteria?

Nothing currently defines the promotion from Green to Blue beyond "once a
feature is vetted and finalized in Green and is used in the game logic." That
describes one feature's promotion, not the dataset's.

### The two options

**Declared.** Cheaper, and will drift — "stable" becomes whatever was most
recently written.

**Earned.** More work, and makes the tier mean something. Candidate criteria:

- every feature in the schema is read by game logic (nothing carried
  speculatively)
- evaluator thresholds tuned against it and frozen
- schema stable — no `Optional` fields still awaiting backfill
- evaluator performance measured and recorded on this exact dataset

### Related: the tier is named twice

`enforce_schema_pipeline(df, mode="dev")` and `ProductionMCQ_Green` both encode
the tier, for different consumers — `mode` steers downstream routing, the model
shapes the DTO. Nothing checks that they agree, so `mode="dev"` with a Blue
model would be accepted and the two halves of the system would disagree about
which tier the data is.

They could be tied together: `mode` selects the model, so the tier is set once.
`mode` is the right input of the two, since it carries more than the model
choice.

### Actions

- [ ] **Decide declared vs earned**, before the promotion step is written.
- [ ] **Write ADR** if earned — the criteria are the decision and need a record.
- [ ] **Update design doc** — the Green/Blue lifecycle block states the
      promotion workflow but not what qualifies a dataset; add whichever answer
      is chosen.
- [ ] **Code — refinery:** `mode` selects the DTO model rather than both being
      passed. Check first whether the model is used anywhere else in the flow;
      if `prepare_parquet_table` is the only consumer, it can take `mode` too
      and the model never appears at the call site.
- [ ] **Code — tracer demo notebook:** the markdown cell records this as open;
      remove that note once resolved.

---

## 7 · `chunk` and `batch` used interchangeably

**Status:** Decided — defer to the shared-utilities extraction
**Date:** 2026-10-02

### The change

Settle on **batch** as the single term for *the set of items sent in one API
call*. Retire "chunk".

### Why

Both words are currently used for the same thing, in both pipelines:

- generation: `chunk_list(chapter_file_paths, batch_size)` yielding
  `chapter_batch`
- enrichment: `chunk_size`, `chunk_index`, alongside `batches` and
  `batch_index`

"Batch" is already load-bearing — `batch_id` is a field on
`GenerationCallEntry` — and it is the standard term for what both passes mean.

This cost real time twice while writing the failure branches: the vocabulary
collision reads as a semantic difference between the passes, and it isn't one.

### One genuine asymmetry to preserve

Enrichment has two counters, generation one:

| | Flat position across all calls | Position within a partition |
|---|---|---|
| Enrichment | `batch_index` (enumerate) | `i // chunk_size`, per question type |
| Generation | `i` (enumerate) | same `i` — only one partition |

They collapse in generation because there is a single chapter list; enrichment
partitions by question type first, then batches within each. The stored field is
the **per-partition** index, since that is what joins back to what the manifest
planned. Enrichment's flat counter is a local for building `call_id`.

### Actions

- [ ] **Code — rename at the extraction:** `chunk_list` → `batch_chapters`,
      `chunk_size` → `batch_size`, `chunk_index` → `batch_index`. Not before —
      a rename across both pipelines mid-feature is churn.
- [ ] **Code — `core/telemetry.py`:** rename `chunk_index` on
      `EnrichmentCallEntry` in the same pass.
- [ ] **Pipeline README:** use one term once the rename lands.

---

## Amendments to existing entries

### Into #2 · Structural gate moves to the producer

Add under **Consequence**, as a second instance of the same rule:

> The same reasoning applies at the container boundary. The refinery enforces
> the **label** — a Pydantic `Literal` on `data_tier` so a mislabelled or
> mixed-tier write fails on construction. The image build enforces the
> **choice** — which file was actually copied in. A schema gate cannot catch a
> selection error, because `Production_Green` is a valid Green file.
>
> The general rule both cases are instances of: **a tier boundary needs a check
> at the boundary, not trust on either side.** And a gate validates that a thing
> is what it claims; it cannot validate that it is the thing you wanted.

Add to **Actions**:

- [ ] **Code — refinery final validation:** `Literal` on `data_tier` in the
      Green and Blue models, so construction is the gate. Confirm first that
      `data_tier` is actually *updated* as records move tiers rather than
      stamped once at Bronze — if it isn't, the field is decorative and the
      `Literal` is what forces it to be load-bearing.
- [ ] **Code — container build:** assert the dataset being copied is
      `Production_Blue`. Check contents, not the filename — a filename can lie,
      and mispointing is the mistake being guarded against. Enforcement by
      absence (the image contains only Blue) covers the runtime; this covers the
      build.

Amend the existing design-doc action to name the table:

- [ ] **Update design doc — P2 Data Tier table:** the Bronze row still reads
      "Raw / Ingestion & Schema Check," which is pre-decision. Post-decision
      Bronze is *structurally gated*, and "Raw" is no longer accurate for data
      that passed a Pydantic gate.

### Into #3 · Receipt readers must tolerate schema drift

Add a third row to **the rule**:

> A key can be missing for three reasons, not two:
>
> | Reason | Accessor |
> |---|---|
> | Same run, same code version | `[]` — a missing key is a bug |
> | Written by an older code version | `.get()` — expected history |
> | **The entry's subclass does not have the field** | **`.get()` — permanent** |
>
> The third is the one that applies today: `quarantined` exists on
> `EnrichmentCallEntry` only, and `save_run_completion` is shared by both
> pipelines, so it reads a field that generation entries will never have. Unlike
> the version case, this does not resolve over time.

Add under **Why**:

> `exclude_none=True` was removed from `append_jsonl` (commit 7). With it,
> an optional field set to `None` was indistinguishable from a field the entry's
> shape does not have, which destroyed the not-recorded versus unset
> distinction. Now `null` means unset and an absent key means the shape lacks
> the field — so `.get()` has exactly one meaning.

Note on the existing **Open question** about `schema_version`: the dev-era
receipts that produced the original `KeyError` have no value as history. Clearing
them and reading with `[]` until the first real run is cheaper than carrying a
compatibility rule from before there is anything to be compatible with. The
version case becomes live the first time a field is added *after* a real run
exists.

---

## Deliberately not added

**Generation call entry is still a dict literal.** A refactor task, not a design
decision. The TODO at the construction site carries the field mismatches
(`questions_saved` → `records_written`, add `source_files`, drop `quarantined`,
`.get()` → `[]`, confirm `prompt_template` vs `prompt_id`).

**One source file = one unit of source content.** Not pending — it is a contract
the pipeline already relies on. Splitting a medium into units (a long article, a
PDF) is a preprocessing concern; the pipeline reads whatever files preprocessing
produced. This belongs in the design doc's Content Factory section directly,
stated as a boundary with a named owner.

