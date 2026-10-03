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

## Content Factory Pipelines

Generation and enrichment of the trivia dataset, orchestrated with **Prefect**.
Inputs and outputs are versioned datasets.

Current pipelines:
- `generate_questions/generate_questions.py` — pass 1, question generation
- `generate_questions/enrich_questions.py` — passes 2 and 3, lexical and
  semantic enrichment (same flow, different config)

Exploratory logic, prompt experimentation, and analysis notebooks live under
`scripts/research/`.

### Running a trial

Every output location is a flow parameter. Passing `--trial` redirects all
artifacts to a separate tree (`TRIAL_*` in `notebook_config`) so a throwaway run
leaves the real run history untouched. Inputs — prompts, source files, the input
DTO list — are unaffected.

## Run artifacts

Four files per pass. If code reads it back, it is an artifact; if only a human
reads it, it is a log.

| File | Answers | Grain |
|-|-|-|
| manifest | what the run planned to do | run |
| questions jsonl | the records produced | question |
| calls jsonl | what each API call cost and returned | call |
| receipt | how the pass closed out | pass |
| quarantine | what failed and why | failure |

Plus Prefect and logger output in `logs/`, which nothing reads programmatically. Principles for reporting:

- **Derive, never duplicate.** Receipt totals are computed from the calls file at
  write time, so the two levels cannot disagree. The markdown report is a
  projection of the receipt, not a second source.
- **One receipt per pass.** All passes in a run share a `run_id`; the end-to-end
  picture is assembled by globbing that id. No single file reports a whole run.

#### Vocabulary

- **record** — one question; a thing in the data
- **entry** — one line in an artifact file *about* records or calls
- **log line** — one line of human-readable narration

So: *a batch of records fails; the branch writes one quarantine entry and one
call entry, and emits one log line.*

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

## Record accounting
records_sent = records_written + records_rejected + batch_loss

Each term is measured at a different point:

| Term | Measured at |
|-|-|
| `records_sent` | send — records included in API requests |
| `records_written` | disk write — records that passed DTO construction and were saved |
| `records_rejected` | DTO construction — returned but failed the structural contract |
| `batch_loss` | the call failing wholesale — no output existed to validate |

The split between rejection and batch loss matters because the fix differs:
rejections point at the prompt, batch loss points at the API or the quota.

The identity holds by construction in the receipt — `records_rejected` is derived
as the remainder. Reconciling it against the questions jsonl and quarantine file
is the run-level delta report's job, which does not exist yet.