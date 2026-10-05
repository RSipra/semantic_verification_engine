# Pipeline Execution & Automation

Prefect-orchestrated pipeline code for the Phase 2 Content Factory, plus the
utility scripts that feed it. Pipelines are run-accounted: every run writes a
manifest, per-call records, and a receipt.

See the [Design Doc](../../docs/00_DESIGN_DOC_AND_ARCHITECTURE.md) for pipeline architecture and decision context.

## Utility Scripts

Lightweight scripts used to automate one-off or infrequent tasks, such as:
- Downloading raw datasets (e.g. from Hugging Face)
- Extracting and formatting the Harry Potter corpus for source grounding in prompts

These scripts are not part of the runtime application and are executed manually or on demand.

---

# Part 1 — Run accounting

Common to every pipeline here. A pipeline that makes LLM calls and writes
artifacts follows this contract regardless of what it produces.

## Artifacts

A run is **reconstructable, not reproducible**: LLM output is non-deterministic,
so a re-run produces different content. These artifacts exist so a run that
cannot be repeated can still be accounted for.

| File | Answers | Grain |
|-|-|-|
| manifest | what the run planned to do | run |
| questions jsonl | the records produced | question |
| calls jsonl | what each API call cost and returned | call |
| receipt | how the pass closed out | pass |
| quarantine | what failed and why | failure |

Prefect and logger output in `logs/`, which nothing reads programmatically. 

## Principles for reporting:

- **Derive, never duplicate.** Receipt totals are computed from the calls file at
  write time, so the two levels cannot disagree. The markdown report is a
  projection of the receipt, not a second source.
- **One receipt per pass.** All passes in a run share a `run_id`; the end-to-end
  picture is assembled by globbing that id. No single file reports a whole run.
- **Receipts are immutable history.** They are never migrated, so the set on disk
  spans code versions and readers must tolerate fields that did not exist when an
  older receipt was written.

## Naming and storage

Artifacts are named `{run_id}_{llm_pass}_{kind}` by `build_run_artifact_path`.
The `llm_pass` segment is what stops one pass overwriting another's files, so
shared helpers never hardcode it — the flow that owns the run supplies it.

Run ids are prefixed by tree: `run*` for the real tree, `test*` for trial runs.
A trial artifact is therefore identifiable even if it lands in the wrong
directory.

See `data/07_pipeline_logs/runs/README.md` for what is kept and why.  

## Vocabulary

- **record** — one question; a thing in the data
- **entry** — one line in an artifact file *about* records or calls
- **log line** — one line of human-readable narration

So: *a batch of records fails; the branch writes one quarantine entry and one
call entry, and emits one log line.*

## Record accounting

```
records_sent = records_written + records_rejected + batch_loss
```

Each term is measured at a different point:

| Term | Measured at |
|-|-|
| `records_sent` | send — records included in API requests |
| `records_written` | disk write — records that passed DTO construction and were saved |
| `records_rejected` | DTO construction — returned but failed the structural contract |
| `batch_loss` | the call failing wholesale — no output existed to validate |

The split between rejection and batch loss matters because the fix differs:
rejections point at the prompt, batch loss points at the API or the quota.

Terms that do not apply to a pass are recorded as `null`, not `0` — zero is a
measurement, and a term that does not apply was never measured. Generation sends
chapters rather than records, so its `records_sent`, `records_rejected` and
`batch_loss` are null.

The identity holds by construction in the receipt — `records_rejected` is derived
as the remainder. Reconciling it against the questions jsonl and quarantine file
is the run-level delta report's job, which does not exist yet.

## Failure modes

A failed batch writes a quarantine entry naming the record ids it lost, a call
entry carrying the `failure_mode`, and a log line.

| Mode | What failed | Tokens | Retry worthwhile |
|-|-|-|-|
| `transport_failure` | the call never completed | none — no response exists | yes |
| `no_candidates` | the call returned, nothing was generated | real | no — the same prompt blocks the same way |
| `response_unparseable` | text returned, not valid JSON | real | yes |

`response_unparseable` entries carry `finish_reason`, which separates a
`MAX_TOKENS` truncation (raise the output budget or shrink the batch) from
genuinely malformed output (fix the prompt).

Quarantine **thresholds warn rather than abort**. Aborting is only affordable
once a resume exists, and normal failure rates are not yet characterised at book
scale — the thresholds build that baseline first.

## Trial runs

Every output location is a flow parameter. `--trial` redirects all artifacts to a
separate tree (`TRIAL_*` in `notebook_config`) so a throwaway run leaves the real
run history untouched. Inputs — prompts, source files, the input DTO list — are
unaffected.

There is no `--trial` flag in Python; a notebook caller passes the four
directories explicitly.

---

# Part 2 - Content Factory Pipelines

Generation and enrichment of the trivia dataset. Inputs and outputs are
versioned datasets.

| Module | Pass | Produces |
|-|-|-|
| `generate_questions/generate_questions.py` | 1 · generation | core question fields from source chapters |
| `generate_questions/enrich_questions.py` | 2 · lexical | surface-level fields |
| `generate_questions/enrich_questions.py` | 3 · semantic | meaning-dependent fields |

Passes 2 and 3 are the same flow with different config. Each pass is a config
entry in `ENRICHMENT_STRATEGY`, not a code path — adding a pass is a
configuration change.

The DTO chain is the validation gate: `DraftQuestion → LexDraftQuestion →
SyntheticStandard`. Nothing mutates in place, and successful construction of the
next DTO *is* the check that the pass produced what it claimed.

Batch size is set by **LLM attention limits established in the tracer**, not by
token or output caps.

### What is specific to these pipelines

- **Generation sends chapters, not records.** The model decides how many
  questions a batch yields, so there is no expected count — hence the null
  accounting terms above, and `source_files` rather than `records_sent` on its
  call entries.
- **Only generation writes a manifest.** An enrichment pass's plan is the
  previous pass's receipt, so there is nothing new for a per-pass manifest to
  declare. A run-level manifest covering all three passes is the orchestrator's
  job.
- **Only generation writes a log file.** Enrichment's Prefect output reaches the
  UI and terminal but nothing on disk — also the orchestrator's job.
- **This module owns the structural contract only.** Semantic quality —
  grounding, hallucination, deduplication — belongs to the validation pipeline.

Exploratory logic, prompt experimentation, and analysis notebooks live under
`scripts/research/`.

---

# Part 3 — Validation pipeline

Not yet pipeline code. Bronze → Silver → Gold validation currently runs in
notebooks (see `notebooks/01_demos/01_tracer/02_medallion_data_validation.ipynb`).

When it is promoted to a pipeline it inherits Part 1 — the same artifacts,
naming, accounting identity and failure modes — and adds its own failure modes
for the checks that are not LLM calls: schema, deduplication, and grounding.
