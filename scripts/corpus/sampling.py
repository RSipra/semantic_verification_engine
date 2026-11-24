"""
Project: SVE (ref implementation: Harry Potter Trivia)
Phase 2: Content Generation (Corpus validation before generation pipeline)

Fidelity review of a profiled corpus: select the sample, show it, promote the result.

Commands (python -m scripts.corpus.sampling [--corpus-root DIR] <command>)
  select   choose the sample from the profiled record (deterministic) and write the
           review CSV: fidelity_evidence/fidelity_evidence_<corpus_id>.csv
  show     print start / middle / end passages of each sampled chapter for side-by-side
           review against the reference edition (--books BOOK_3 BOOK_7 to filter)
  promote  check the reviewed CSV and the references file, then certify the record:
           one FidelitySample per book, evidence files bound by sha256, status
           `certified`. Any problem: refuse, write nothing, exit 1.

Hand-edited inputs (validated when read)
  review CSV       one SampleReviewRow per sampled chapter; the reviewer fills result + notes
  references file  fidelity_references_<corpus_id>.json: reference edition per book

Exit codes: 0 = done or nothing to do; 1 = refused (problems printed).

Record structure: see corpus_models. Workflow, sampling plan and promote checks:
docs/adrs/ADR-P2-026_specs.md (sections 1, 4, 5, 6).
"""
import argparse
import sys
from pathlib import Path
from statistics import quantiles
import logging
import random
from collections import defaultdict, Counter
from collections.abc import Callable
from typing import TypeVar
from datetime import date

import pandas as pd
from pydantic import ValidationError

from core.constants import Book
from scripts.corpus.corpus_models import (CorpusSchema, BookSchema, SampleReviewRow, Labels,
                                          DEFAULT_CORPUS_ROOT, record_path, FidelityReferences,
                                          read_corpus_record, file_sha256, FidelitySample,
                                          hash_evidence,)


logger = logging.getLogger(__name__)

## Helpers

def iqr_outliers(chapters: dict[int, int], multiplier: float = 1.5) -> set[int]:
    """
    Return chapter numbers whose word counts are outliers by the IQR method.

    Outliers lie strictly below Q1 - multiplier*IQR or strictly above Q3 + multiplier*IQR
    (both tails: short → possible truncation, long → possible merged chapters).
    Quartiles use method='inclusive': the chapters are the whole book (a population,
    not a sample); this also matches numpy's default.

    Returns an empty set when there is no basis for outliers: fewer than 4 chapters,
    or IQR = 0 (all chapters the same length).
    """

    if len(chapters) < 4:
        logger.debug("fewer than 4 chapters: no basis for IQR outliers")
        return set()  # not enough data to compute IQR

    # calculate outlier fences (Q1 - k*IQR, Q3 + k*IQR)
    q1, _, q3 = quantiles(chapters.values(), n=4, method="inclusive")   # median unused
    iqr = q3 - q1

    if iqr == 0:
        logger.debug("IQR is zero, all chapters have the same length")
        return set()  # all chapters have the same length

    lower_fence = q1 - multiplier * iqr
    upper_fence = q3 + multiplier * iqr

    # filter chapters
    return {n for n, words in chapters.items() if words < lower_fence or words > upper_fence}


def select_book_sample(book_record: BookSchema,
                                corpus_id: str) -> dict[int, list[Labels]]:
    """
    Select chapters for fidelity review from one book: chapter number → reasons.

    Rules: first, last, shortest, longest, IQR outliers (both tails), plus a seeded random
    pick from the remaining chapters —> 1 if every chapter's title is in its text, else 2.
    Seeded per book (f"{corpus_id}_{book.name.value}") so the same corpus always gives the
    same sample, independent of other books.
    """

    wordcounts = {n: ch.word_count for n, ch in book_record.chapters.items()}
    labels: dict[int, list[Labels]] = defaultdict(list)

    labels[min(wordcounts)].append('first')
    labels[max(wordcounts)].append('last')
    labels[min(wordcounts, key=lambda n: wordcounts[n])].append('shortest')
    labels[max(wordcounts, key=lambda n: wordcounts[n])].append('longest')
    for n in iqr_outliers(wordcounts):
        labels[n].append('iqr_outlier')

    # list is sorted so that random selection with seed is deterministic
    remaining_chapters = sorted(set(wordcounts) - set(labels))
    n_random = 1 if all(ch.title_in_text for ch in book_record.chapters.values()) else 2
    rng= random.Random(f"{corpus_id}_{book_record.name.value}")
    for n in rng.sample(remaining_chapters, k=min(n_random, len(remaining_chapters))):
        labels[n].append('random')

    return dict(sorted(labels.items()))


def select_corpus_sample(record: CorpusSchema) -> list[SampleReviewRow]:
    """
    Sample chapters across all books of a profiled corpus: one SampleReviewRow per chapter.
       
    Calls select_book_sample per book; rows are sorted by book, then chapter, so the same
    corpus always yields the same file. result and notes start empty and are filled in by
    the reviewer (see ADR-P2-026 for what to record).
    """

    # for each book in corpus, select chapters for review and create a df for manual review
    rows = [
            SampleReviewRow(
                corpus_id=record.corpus_id,
                book=book_name,
                chapter=chapter,
                reason=labels)
            for book_name, book in record.content.items()
            for chapter, labels in select_book_sample(book, record.corpus_id).items()
        ]
    return sorted(rows, key=lambda r: (r.book.value, r.chapter))


def evidence_path(corpus_root: Path, corpus_id: str) -> Path:
    """Where the fidelity review CSV for this corpus lives."""
    return corpus_root / "fidelity_evidence" / f"fidelity_evidence_{corpus_id}.csv"


def write_evidence(rows: list[SampleReviewRow], path: Path) -> None:
    """
    Write review rows to CSV (reason as a JSON list via SampleReviewRow). Overwrites: callers
    decide whether writing is allowed (see main).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([r.model_dump(mode="json") for r in rows]).to_csv(path, index=False)


def read_evidence(path: Path) -> list[SampleReviewRow]:
    """
    Read the (hand-edited) review CSV back into validated rows. dtype=str and
    keep_default_na=False hand cells over exactly as written, so empty results stay ''.
    
    Returns List[SampleReviewRow]
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [SampleReviewRow.model_validate(r) for r in df.to_dict("records")]

PASSAGE_LENGTH = 300

def passages(text: str, length: int = PASSAGE_LENGTH) -> dict[str, str]:
    """
    Start, middle and end excerpts of a chapter for side-by-side review (whitespace collapsed).
    """
    flat = " ".join(text.split())
    mid = len(flat) // 2
    return {
        "START": flat[:length],
        "MIDDLE": flat[max(0, mid - length // 2): mid + length // 2],
        "END": flat[-length:],
    }

CHECK_SCOPE = (f"start, middle, end passages (~{PASSAGE_LENGTH} chars each) "
               "shown by `sampling show`, compared manually against the reference")

def references_path(corpus_root: Path, corpus_id: str) -> Path:
    """create standard reference path for fidelity reference records"""
    return corpus_root / "fidelity_evidence" / f"fidelity_references_{corpus_id}.json"


def read_references(path: Path) -> FidelityReferences:
    """read the fidelity evidence files"""
    return FidelityReferences.model_validate_json(path.read_text(encoding="utf-8"))


def print_problems(header: str, problems: list[str]) -> None:
    """helper to print problems list"""
    print(f"{header}: {len(problems)} problem(s)")
    for p in problems:
        print(f"  - {p}")


def check_changed_chapters(corpus_root:Path, record:CorpusSchema) -> list[str]:
    """ Chapters whose file is missing or whose bytes differ from the recorded sha256."""
    changed = []
    # loop over contents dict in record, sorted by key (book name)
    for book in sorted(record.content, key=lambda b: b.value):
        book_record = record.content[book]

        # for each chapter in the book record - check sha
        for number, chapter in sorted(book_record.chapters.items()):
            # read file
            path = corpus_root / chapter.filename
            if not path.is_file():
                changed.append(f"{book.value} ch {number}: file missing ({chapter.filename})")
            # check the sha.
            elif chapter.sha256 != file_sha256(path):
                changed.append(
                    f"{book.value} ch {number}: changed since profiling ({chapter.filename})")
    return changed


def summarize_book(rows: list[SampleReviewRow], reference: str, today: date) -> FidelitySample:
    """
    Summarise one book's review rows into its FidelitySample for the certified record.

    Args:
        rows: this book's rows from the review CSV (one per sampled chapter). Already
            checked by promote: every result is "pass", and they cover the planned sample.
        reference: the reference edition this book was checked against
            (FidelityReferences.references[book]).
        today: certification date; passed in so tests can fix it.

    Returns:
        FidelitySample with: the sampled chapters (sorted); a sampling strategy built from
        the rows (review round(s) + label counts, e.g. "round 1: first ×1, random ×2");
        the fixed check scope; the reference; result "pass"; date_checked = today.
    """
    # how many rounds completed in manual review, 1 or 2
    rounds = ", ".join(str(n) for n in sorted({r.round for r in rows}))
    # aggregation of sampling chapter labels across the book
    counts = Counter(label for r in rows for label in r.reason)
    # readable summary of label with count
    labels = ", ".join(f"{label} ×{n}" for label, n in sorted(counts.items()))
    # construct sample dto
    return FidelitySample(
        chapters=sorted(r.chapter for r in rows),
        sampling_strategy=f"round {rounds}: {labels}",
        check_scope=CHECK_SCOPE,
        reference=reference,
        result="pass",
        date_checked=today,
    )
# define placeholder for type determined at function call.
T = TypeVar('T')

def load_input(label: str, path: Path, reader: Callable[[Path],T], problems: list[str],
               *, hint: str="", display_path: Path | None = None) -> T | None:
    """
    Wrapper around a reader: call `reader(path)` and turn its expected failures into
    entries in `problems` instead of exceptions.

    The reader does the reading and validation (e.g. read_evidence, read_references,
    read_corpus_record); this wrapper only handles its failures, so every input is
    reported the same way:
      - missing file (FileNotFoundError)        -> "<label> not found: <file><hint>"
      - unreadable (PermissionError)            -> "<label> unreadable (permission denied): <file>"
      - invalid (ValidationError, ParserError)  -> "<label> invalid: <file>" + details
    In those cases it returns None and does not raise; the caller decides what to do
    with `problems` (promote: print them, exit 1). Any other exception is a bug and is
    not caught.

    Args:
        label: what the input is, used in messages (e.g. "review CSV").
        path: the argument passed to `reader`. Usually the file itself.
        reader: function that reads and validates the input (e.g. read_evidence).
        problems: list the failure message is appended to (go/no-go: the caller decides).
        hint: appended to the "not found" message, e.g. " (run `sampling select` first)".
        display_path: the file to show in messages, when `path` is not the file itself.
            Currently only the corpus record: read_corpus_record takes corpus_root (a
            folder), so the message shows record_path(corpus_root) instead. Default: path.

    Returns:
        The reader's result, or None if the file is missing, unreadable or invalid.
        Unexpected errors (bugs) are not caught.
    """
    message_path = display_path or path
    try:
        return reader(path)

    except FileNotFoundError:
        problems.append(f"{label} not found: {message_path}{hint}")
    except PermissionError:
        problems.append(f"{label} unreadable (permission denied): {message_path}")
    except (ValidationError, pd.errors.ParserError) as e:
        problems.append(f"{label} invalid: {message_path}\n{e}")

    return None


## Orchestrators

def run_select(corpus_root: Path) -> int:
    """
    `sampling select`: choose the fidelity sample for a profiled corpus and write the review CSV.

    Does nothing (exit 0) if the corpus is not `profiled`, or if a review CSV already exists for
    this corpus_id (it may hold the reviewer's results; delete it to reselect).
    """
    # load corpus record from json
    record = read_corpus_record(corpus_root)

    # check corpus status
    if record.status != "profiled":
        print(f"corpus {record.corpus_id} is {record.status}: nothing to sample")
        return 0

    # check if evidence file exists for corpus
    write_path = evidence_path(corpus_root, record.corpus_id)
    if write_path.exists():
        print(f"sample already selected for corpus {record.corpus_id}: {write_path} "
              "(fill in results, or delete the file to reselect)")
        return 0

    # select corpus samples
    samples = select_corpus_sample(record)

    # write evidence file
    write_evidence(samples, write_path)
    print(f"{len(samples)} chapters selected across {len(record.content)} books → {write_path}")
    return 0


def run_show(corpus_root:Path, books:set[Book]|None=None) -> int:
    """
    `sampling show`: print start / middle / end passages of each sampled chapter, for
    comparison against the reference copy. All books, or only `books`.
    """
    # load corpus record from json
    record = read_corpus_record(corpus_root)

    # read evidence file
    path = evidence_path(corpus_root, record.corpus_id)
    if not path.exists():
        print(f"no sample selected yet for corpus {record.corpus_id}: run `select` first")
        return 1

    rows =  [r for r in read_evidence(path) if books is None or r.book in books]
    if not rows:
        print("no sampled chapters for the selected book(s); run `select` first.")
        return 0

    # gather chapters text
    for row in rows:
        chapter = record.content[row.book].chapters[row.chapter]
        text = (corpus_root / chapter.filename).read_text(encoding="utf-8")
        print(f"\n=== {row.book.value} ch {row.chapter} · '{chapter.title}' · "
              f"{', '.join(row.reason)} · round {row.round} ===")
        for label, excerpt in passages(text).items():
            print(f"\n[{label}]\n{excerpt}")

    return 0


def run_promote(corpus_root:Path, today: date | None = None)-> int:
    """
    `sampling promote`: certify a profiled corpus from its review CSV and references.

    Refuses (exit 1, writes nothing) unless every check passes; exit 0 if already certified.
    Checks by level (spec section 6): 0 status, 1 inputs readable, 2 identity,
    3 chapters unchanged, 4 sample complete, 5 all pass; then 6 build, validate, write.
    """
    # setup
    problems: list[str] = []
    today = today or date.today()

    # 1a. read the record (validated by the model); needed for the status check
    record = load_input("corpus record",
                        corpus_root,
                        read_corpus_record,
                        problems,
                        hint=" (run qualify_corpus first)",
                        display_path=record_path(corpus_root))
    if record is None:
        print_problems("promote refused", problems)
        return 1

    # 0. status: only a profiled record can be promoted
    if record.status == "certified":
        print(f"corpus {record.corpus_id} already certified: nothing to do")
        return 0
    if record.status != "profiled":
        print_problems("promote refused",
                       [f"record status is {record.status!r}: re-profile the current data"])
        return 1

    # 1b. evidence inputs readable: review CSV and references file
    csv_path = evidence_path(corpus_root, record.corpus_id)
    refs_path = references_path(corpus_root, record.corpus_id)

    evidence_rows = load_input("review CSV",
                               csv_path,
                               read_evidence,
                               problems,
                               hint=" (run `sampling select` first)",)

    evidence_refs = load_input("references file",
                               refs_path,
                               read_references,
                               problems,)

    if evidence_rows is None or evidence_refs is None:
        print_problems("promote refused", problems)
        return 1

    # 2. identity: evidence belongs to this corpus
    bad_ids = sorted({r.corpus_id for r in evidence_rows if r.corpus_id != record.corpus_id})
    if bad_ids:
        problems.append(f"review CSV rows carry corpus_id {bad_ids}, "
                         f"expected {record.corpus_id}")
    if evidence_refs.corpus_id != record.corpus_id:
        problems.append(f"references file carries corpus_id {evidence_refs.corpus_id}, "
                         f"expected {record.corpus_id}")
    if problems:
        print_problems("promote refused", problems)
        return 1

    # 3. data unchanged: chapter files still match the profiled sha256
    changed_chapters = check_changed_chapters(corpus_root, record)
    if changed_chapters:
        problems.append("chapter files differ from the profiled record: "
                        + "; ".join(changed_chapters)
                        + " (restore files or re-profile before promoting)")
        print_problems("promote refused", problems)
        return 1

    # 4. sample complete: CSV == regenerated plan; every book has a reference
    planned = {(r.book, r.chapter) for r in select_corpus_sample(record)}
    reviewed = {(r.book, r.chapter) for r in evidence_rows}
    missing = sorted(planned - reviewed)
    extra = sorted(reviewed - planned)
    if missing:
        problems.append("planned chapters not in the review CSV: "
                        + ", ".join(f"{b.value} ch {n}" for b, n in missing))
    if extra:
        problems.append("review CSV chapters not in the planned sample: "
                        + ", ".join(f"{b.value} ch {n}" for b, n in extra))
    no_ref = sorted(b.value for b in set(record.content) - set(evidence_refs.references))
    if no_ref:
        problems.append(f"no reference for: {', '.join(no_ref)}")

    # 5. outcome: every row reviewed and passed
    for row in evidence_rows:
        where = f"{row.book.value} ch {row.chapter}"
        if row.result == "":
            problems.append(f"{where}: not reviewed (result is blank)")
        elif row.result == "fail":
            problems.append(f"{where}: failed review (escalate per ADR-P2-026, round 2)")

    # go / no-go for levels 4 and 5 (collected together)
    if problems:
        print_problems("promote refused", problems)
        return 1

    # 6. build the certified record, validate (backstop), write
    data = record.model_dump()
    for book in sorted(record.content, key=lambda b: b.value):
        # read the evidence rows for book from the evidence file
        book_rows = [r for r in evidence_rows if r.book == book]
        sample = summarize_book(book_rows, evidence_refs.references[book], today)
        data["content"][book]["fidelity_sample"] = sample.model_dump()
    data.update(status="certified", certification_method="manual_review",
                date_certified=today,
                evidence_files=hash_evidence(corpus_root, [csv_path, refs_path]))
    certified = CorpusSchema.model_validate(data)
    record_path(corpus_root).write_text(certified.model_dump_json(indent=2), encoding="utf-8")

    print(f"certified corpus {certified.corpus_id}: {len(certified.content)} books, "
          f"{len(evidence_rows)} chapters reviewed, all pass")
    return 0

def main(argv: list[str]|None = None):
    """CLI for the fidelity check: `select`, then `show` and `promote`
    (see module docstring)."""

    # create parser: arguments for running module
    parser = argparse.ArgumentParser(description="Fidelity sampling for the corpus.")
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT,
                        help="folder holding the corpus record and chapter files")

    # define subcommands (sampling steps) to run
    steps = parser.add_subparsers(dest="step", required=True)
    steps.add_parser("select", description="select the corpus sample and write the review CSV")
    show = steps.add_parser("show", help="print start/middle/end passages of sampled chapters")

    show.add_argument("--books", nargs="+", choices=[b.name for b in Book],
                  help="only these books (e.g. BOOK_3 BOOK_7); default: all")
    steps.add_parser("promote", help="certify the corpus from the reviewed sample")
    # run the cli subcommands + arguments
    args = parser.parse_args(argv)

    # call the function for the chosen step, passing the parsed folder
    if args.step == 'select':
        return run_select(args.corpus_root)
    if args.step == 'show':
        books = {Book[name] for name in args.books} if args.books else None
        return run_show(args.corpus_root, books)
    if args.step == 'promote':
        return run_promote(args.corpus_root)
    return 1  # run failure

if __name__ == "__main__":
    sys.exit(main())
