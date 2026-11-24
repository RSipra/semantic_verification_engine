# ADR-P2-026 Specification: Corpus Qualification and Preflight

**Decision record:** [ADR-P2-026.md](ADR-P2-026.md) — why this exists. This file says *how* it works and is
updated as the implementation changes.

**Contract:** `scripts/corpus/corpus_models.py` · **Jobs:** `qualify_corpus.py`, `sampling.py`, `preflight.py` (next)


## 1. Workflow

| Step | Command | Output | Record status |
|---|---|---|---|
| 1. Profile | `python -m scripts.corpus.qualify_corpus` | `corpus_record.json` | `profiled` |
| 2. Select sample | `python -m scripts.corpus.sampling select` | `fidelity_evidence/fidelity_evidence_<corpus_id>.csv` | `profiled` |
| 3. Review | `python -m scripts.corpus.sampling show --books ...` | reviewer fills `result` + `notes` in the CSV; writes `fidelity_references_<corpus_id>.json` | `profiled` |
| 4. Promote | `python -m scripts.corpus.sampling promote` (planned) | fidelity samples + `evidence_files` written to the record | `certified` |
| 5. Version | `dvc add data/06_books` → `dvc push` → commit `data/06_books.dvc` | data commit | — |
| Every run | preflight (planned, commit B) | go / no-go before any API call | must be `certified` |

All commands accept `--corpus-root`; tests always pass a temporary root and never write to `data/06_books`.


## 2. Lifecycle rules
- `profiled` — every chapter measured and fingerprinted; proves presence and identity, not correctness.
  Not usable by the pipeline.
- `certified` — a fidelity sample of every book passed against a reference edition; evidence bound by hash.
  Required for any pipeline run, trials included.
- `superseded` — replaced by a newer record (data changed → new `corpus_id`).
- Review is performed on the profiled record, never before it: evidence must refer to fixed bytes.
- **Go/no-go:** every job collects all problems in one pass and writes nothing if there are any (exit 1).
- **Overwrite rule (profiling):** a `certified` record with an unchanged `corpus_id` is left untouched; if the
  data changed, the record is replaced as `profiled` and certification is cleared.
- **Strict gate:** `certified` is required for every pipeline run, trials included. Preflight's own tests use
  fake corpora (pytest), so they never depend on certification.


## 3. Profiling checks (job 1)
- Per chapter, cheapest first: file exists → not empty → decodes as UTF-8 → title matches the table of contents
  (books whose files carry titles) → record built (sha256 of raw bytes; counts on decoded text).
- Per book: no unexpected files; chapter count equals the table of contents.
- Titles come from a **table-of-contents snapshot** (fan-compiled CSV, pinned commit `57acafc1…`, committed;
  the script never calls the network).
- Reviewed discrepancies are recorded as explicit **title exceptions** (title + reason) — documented, never
  hidden by loosening the comparison.


## 4. Sampling plan (per book, deterministic)
- **Always:** first, last, shortest and longest chapter (by `word_count`).
- **Outliers:** chapters outside 1.5 × IQR of the book's word counts, both tails (short → truncation,
  long → merged chapters). Inclusive quartiles, strict fences; none if fewer than 4 chapters or IQR = 0.
- **Random:** 1 chapter from the rest; 2 if the book's files carry no titles (books 4, 7). Seeded with
  `"<corpus_id>_<book>"` over a sorted pool, so the same corpus always yields the same sample.
- **Escalation:** one fail → +3 chapters for that book (round 2; neighbours too for a swap); a second fail →
  the book fails and the corpus cannot be certified until fixed. *Implemented so far: promote refuses on any fail.*
- Earlier EDA checks are recorded as notes; acceptance rests on the current sample only.


## 5. Fidelity review
**Reference editions** — recorded per book in `fidelity_references_<corpus_id>.json`
(UK Pottermore e-books, ISBN per book, borrowed via a public library).

**Check scope** — start, middle and end passages (~300 characters each) of each sampled chapter, read with
`show`, compared against the reference by a person.

**Pass criterion**
- **Pass:** the right content, complete, in the right chapter. Edition wording and encoding differences are
  acceptable and noted.
- **Fail:** missing, truncated, swapped or garbled content.

**Note tags** (one line per chapter in the CSV `notes`)

| Tag | Meaning |
|---|---|
| `EDITION` | US (corpus) vs UK (reference) differences: quote style, punctuation, spelling, wording |
| `DASH` | dash encoding (book 3 `--`, book 4 ` - `, book 7 `¨C`); noted once per book |
| `QUOTE` | opening quote dropped where a chapter opens with dialogue |
| `OCR` | misread character or punctuation |

**Method notes**
- Read `show` output on screen or redirect it to a file (`show ... > review.txt`); copying from a wrapped
  terminal can drop spaces and create false run-together words.
- Edit the CSV in a plain-text editor, not a spreadsheet (spreadsheets rewrite quoting and types).

**Handling constraints**
- Reference e-books are used only for a person's side-by-side reading. Their text is never copied into notes,
  the CSV or the repository, and never passed to any tool or model (the e-books reserve text-and-data mining
  and AI training). Notes describe differences; they do not quote the reference.


## 6. Promotion and evidence binding
**Promote** (`python -m scripts.corpus.sampling promote`) certifies a profiled corpus. Checks run in order;
any problem means refuse — exit 1, write nothing. Root-cause levels stop at once; levels 4 and 5 are
reported together.

| Level | Check | On failure |
|---|---|---|
| 0. Status | record is `profiled` | `certified` → exit 0, nothing to do; anything else → refuse |
| 1. Inputs | record, review CSV and references file exist and validate | refuse (stop) |
| 2. Identity | every CSV row's and the references file's `corpus_id` equals the record's | refuse (stop) |
| 3. Data unchanged | every chapter file's sha256 equals the record's | refuse (stop): restore files or re-profile |
| 4. Sample complete | CSV `(book, chapter)` set equals the regenerated `select` plan; every book has a reference | refuse (collect) |
| 5. Outcome | no blank `result`; every row `pass` | refuse (collect); a fail → escalate (round 2) |
| 6. Write | build the certified record, validate it through `CorpusSchema`, write | model validators are the backstop |

On success, for each book it writes a `FidelitySample`: chapters (sorted), sampling strategy (review round(s)
and label counts, e.g. `round 1: first ×1, random ×2`), check scope, reference, result `pass`, date. It sets
`certification_method = manual_review` and `date_certified`, and stores `evidence_files`: the sha256 of the
review CSV and the references file, keyed by path relative to `corpus_root`. `[profile]` fields are never
changed.

**Preflight** (planned, commit B) runs on the selected chapters before any API setup
(`configure_api` / `measure_template_tokens`) and stops the run, with zero API calls, if:
- the record is not `certified`;
- an expected chapter file is missing, or the chapter count differs;
- a chapter's sha256 differs from the record — recorded character / word counts are used only to *explain* the
  mismatch (emptied / truncated / edited in place), never to decide it;
- an evidence file is missing or edited (`changed_evidence`): the certificate no longer describes the evidence.

DVC's own hashes (`dvc status`) are an independent second layer: different software detecting the same changes.

**Re-certification** (planned) — a legitimate evidence correction needs an explicit `promote --recertify`, allowed only
for a certified record whose `corpus_id` still matches the evidence. It re-runs every promote check and rewrites
the fidelity samples, `evidence_files` and `date_certified`. Changes to chapter data are not re-certification:
they change `corpus_id` and re-profile.

**Date rule** — every promote stamps the current date; the reason for a re-certification goes in the data commit
message. Prior certifications live in Git/DVC history.


## 7. Corpus record v0.1
- **Corpus:** `schema_version` ("0.1", exact match), `corpus_id` (hash of all chapter checksums — changes if and
  only if the data changes), `status`, `provenance` (`source_type`, `origin`, `acquired_from`, extraction script
  and commit), `certification_method`, `date_certified`, `evidence_files`, `corpus_root`, `scope`
- **Book:** `expected_chapters`, `published_year`, `isbn` (corpus edition; null until confirmed), profiling
  `evidence`, `fidelity_sample`
- **Chapter:** `title`, `title_in_text`, `number`, `filename`, `character_count`, `word_count`, `sha256`
- **Invariants:** `certified` requires a method, a date, `evidence_files` and a passing sample for every book;
  evidence paths stay inside `corpus_root` and hashes are sha256 hex; chapter keys equal `chapter.number`;
  sampled chapters exist; stored `corpus_id` equals the computed one; unknown fields rejected.


## 8. Evidence log
**Profiling (2026-11-09)**
- Run 1: 60 problems — zero-padded file names (`chapter_01`); fixed in the script, file check compares names.
- Run 2: 41 problems — book 4 files carry a title in ch 1 only → treated as no titles in text.
- Title check, book 3: ch 8 "FAT FADY" and ch 18 "PADDFOOT" are corpus typos (table of contents correct);
  ch 19 is a table-of-contents error (file matches the published title). All recorded as title exceptions.
- Final run: passed — 3 books, 96 chapters, `corpus_id 680db04cf48248ce`, `profiled`.
- Run-together words reported at profiling ("fewseconds", "magicto"): **to re-verify** with `grep` on the files —
  the review showed that terminal copying creates the same pattern.

**Fidelity review (2026-11)**
- 17 chapters: book 3 — 1, 12, 18, 20, 21, 22; book 4 — 1, 4, 23, 29, 32, 37; book 7 — 1, 2, 33, 36, 37.
- All pass. Findings: `EDITION` differences throughout (consistent with a US corpus against UK references),
  book-wide `DASH` encodings, `QUOTE` at dialogue-opening chapters, occasional `OCR` misreads.
- Run-together words seen during review were terminal copy artefacts (absent from the files).


## 9. Deferred (add when a consumer needs them)
- **Graded gate:** trials accept `profiled` with a recorded warning — revisit if the corpus grows and
  certification becomes slow.
- **Certification history:** append-only list of certification events; until then Git/DVC history serves.
- **Record revision:** integer bumped on any record change, for run manifests to cite.
- **Semantic `schema_version`:** MAJOR.MINOR at 1.0; exact match while 0.x.
- **Recertification kind** (review vs correction) to keep `date_checked` on corrections.
- **Provenance detail:** package / extraction commits; corpus edition ISBN.
- **Corpus onboarding:** garbled-text heuristic, LLM coherence review (experiment), outlier review — for books 1, 2, 5, 6.
- **Text normalisation (E2):** dash styles and dropped opening quotes, for source-quote matching.
- **Per-book profile notes:** each book's evidence notes list only its own exceptions.
- **Per-book certification** *(before adding the next book)*: book-level hash and sampling seed; evidence files
  per book; unchanged books carry their passing sample forward, so adding a book needs review of that book only.
- **`superseded` status:** nothing writes it (re-profiling replaces the record); keep or drop.
- **Round 2 rows:** promote currently requires an exact match with the plan; with escalation, extra rows are
  allowed only when `round == 2`.


## 10. Risks (detail)
- **Transcription errors in body text:** title typos suggest similar errors in the body; accepted by the pass
  criterion, but they affect exact source-quote matching (E2).
- **Books 4 and 7 alignment:** files carry no titles, so file ↔ content alignment rests on the fidelity sample —
  mitigated by an extra random chapter per book and by matching each START against the e-book chapter start.
- **Fan-compiled table of contents:** shown to contain an error (book 3 ch 19); every mismatch is reviewed before
  being recorded as an exception.


## 11. Production / regulated deltas
- **Production:** a licensed source with supplier-published checksums or signed artifacts; data contracts on
  ingestion; a documented sampling plan; a data card; independent sign-off; reference material licensed for the
  intended use (including any automated comparison).
- **Regulated:** supplier qualification, data-integrity principles (ALCOA+), audit trails, re-qualification
  under change control.
- **Out of scope here:** data ownership, access and retention policies.
