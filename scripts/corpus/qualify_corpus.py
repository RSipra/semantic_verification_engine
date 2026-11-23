"""
Project: SVE (ref implementation: Harry Potter Trivia)
Phase 2: Content Generation (Corpus validation before generation pipeline)

qualify_corpus— create a graded corpus record (corpus, book, chapter levels -
job 1 of the corpus trust boundary (ADR-P2-026): profile the corpus.)
======================================================================
 
Profiles every chapter of the selected books deterministically and writes the corpus
record (status `profiled`) that preflight (job 2) later verifies against. Field
meanings and invariants live in `corpus_models`; this module documents only how the
record is produced.
 
Flow (go/no-go)
1. Load the table-of-contents snapshot (chapter number → title per book) and check
   each book's chapter numbers run 1..N.
2. For each expected chapter: file exists → not empty → decodes as UTF-8 → title
   matches (books whose files carry titles) → build the ChapterSchema
   (sha256 of raw bytes; counts on decoded text). Then flag unexpected files and a
   chapter-count mismatch per book.
3. Every problem is collected in one pass. If there are any, they are printed grouped
   by book and NOTHING is written (exit 1): a record only ever describes a corpus that
   passed its own checks.
4. Otherwise build the CorpusSchema (corpus_id computed from the checksums) and write
   <corpus_root>/corpus_record.json, following the overwrite rule:
     - existing `certified` record with the same corpus_id → unchanged, nothing written
     - existing record with a different corpus_id → replaced (certification cleared if
       it was certified: the evidence referred to different bytes)
     - otherwise → written / replaced. DVC keeps previous versions.
 
Scope: produces `profiled` only. Promotion to `certified` (fidelity sample evidence) is
a later step. The script never calls the network: the toc is a committed snapshot.
 
Usage (repo root):
    python -m scripts.corpus.qualify_corpus                 # all books, write record
    python -m scripts.corpus.qualify_corpus --dry-run       # check only, never write
    python -m scripts.corpus.qualify_corpus --books BOOK_3  # subset (record covers only these)

Re-profiling after a code change (order matters)
  The record cites the code that produced it (evidence.source = qualify_corpus.py@<HEAD>).
  Uncommitted edits are not in HEAD, so commit the code BEFORE profiling:
    1. commit code changes       git commit
    2. profile                   python -m scripts.corpus.qualify_corpus --corpus-root data/06_books
    3. check the source SHA      grep '"source"' data/06_books/corpus_record.json  (== git rev-parse HEAD)
    4. version + commit data     dvc add data/06_books && dvc push && git add data/06_books.dvc && git commit    

"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

import pandas as pd
from pydantic import ValidationError

from core.constants import Book
from scripts.corpus.corpus_models import (
    BookSchema, ChapterSchema, CorpusSchema, ProfileEvidence, Provenance, compute_corpus_id,
    DEFAULT_CORPUS_ROOT, record_path)

# Extraction commit number:
EXTRACTION_COMMIT = "4853d448ebef0fce3806bf2e53cef5dd100f0c3f"

# Reviewed title discrepancies: (book, chapter) → (title to record, reason).
TITLE_EXCEPTIONS: dict[tuple[Book, int], tuple[str, str]] = {
    (Book.BOOK_3, 8):  ("Flight of the Fat Lady", "corpus text typo 'FAT FADY'; toc correct"),
    (Book.BOOK_3, 18): (
        "Moony, Wormtail, Padfoot, and Prongs", "corpus text typo 'PADDFOOT'; toc correct"),
    (Book.BOOK_3, 19): (
        "The Servant of Lord Voldemort",
        "toc snapshot error; file matches published title (verified online, 2026-11-09)"),
    # book 4: toc snapshot errors; US edition contents page per Scholastic excerpt
    # (scholastic.com/hpread/HP_Book4_Chapter_Excerpt.pdf, ISBN 978-0-439-13959-5), checked 2026-11-22
    (Book.BOOK_4, 5): (
        "Weasleys’ Wizard Wheezes",
        "toc snapshot error ('Weasley’s'); US edition title per Scholastic contents, 2026-11-22"),
    (Book.BOOK_4, 28): (
        "The Madness of Mr. Crouch",
        "toc snapshot error (UK 'Mr'); US edition title per Scholastic contents, 2026-11-22"),

    # book 7: toc snapshot errors; wording per US 1st ed. contents
    # (Scholastic, illus. GrandPré; lib.ecu.edu catalogue record 1079452, checked 2026-11-22)
    (Book.BOOK_7, 6): ("The Ghoul in Pajamas",
                       "toc snapshot error (UK spelling 'Pyjamas'); US edition title per library catalogue, 2026-11-22"),
    (Book.BOOK_7, 13): ("The Muggle-Born Registration Commission",
                        "toc snapshot error ('Committee'); US edition title per library catalogue, 2026-11-22"),
    (Book.BOOK_7, 16): ("Godric’s Hollow",
                        "toc snapshot typo ('Hallow'); US edition title per library catalogue, 2026-11-22"),
}

# Same for every book: where the titles came from.
TOC_NOTE = ("toc: HP_Chapters.csv from github.com/sharanyavb/harry-potter@57acafc1a9e5ed3f7c89a0d19f69d32806afbde9 "
            "(fan-compiled; mixes US and UK forms)")

# Per book: how the recorded titles were verified.
TITLE_VERIFICATION: dict[Book, str] = {
    Book.BOOK_3: "titles in text: every chapter checked against the toc",
    Book.BOOK_4: ("titles not in text (ch 1 only): all 37 verified against the US edition contents "
                  "(Scholastic excerpt, ISBN 978-0-439-13959-5), 2026-11-22"),
    Book.BOOK_7: ("titles not in text: ch 1–36 verified against the US 1st ed. contents "
                  "(Scholastic 2007, ISBN 978-0-545-01022-1; lib.ecu.edu catalogue record 1079452), "
                  "2026-11-22; ch 37 'Epilogue' is untitled in the contents"),
}


def book_notes(book: Book) -> str:
    """
    Profile notes for one book: toc source, how titles were verified, this book's exceptions only.
    """
    exceptions = [f"ch {n}: {reason}"
                  for (b, n), (_, reason) in sorted(TITLE_EXCEPTIONS.items()) if b == book]
    parts = [TOC_NOTE, TITLE_VERIFICATION[book]]
    if exceptions:
        parts.append("title exceptions: " + "; ".join(exceptions))
    return " | ".join(parts)

# --- configuration -----------------------------------------------------------------
TOC_RELATIVE_PATH = Path("reference/hp_chapters_toc.csv")   # snapshot, inside corpus_root
SCHEMA_VERSION = "0.1"

# Join key into the toc snapshot's "Book Number" column (names differ between sources).
TOC_BOOK_NUMBER: dict[Book, int] = {Book.BOOK_3: 3, Book.BOOK_4: 4, Book.BOOK_7: 7}

# Whether chapter files start with their title (book 3 yes; book 4 only ch 1, so treated as no;
# book 7 no). Set, not
TITLE_IN_TEXT: dict[Book, bool] = {Book.BOOK_3: True, Book.BOOK_4: False, Book.BOOK_7: False}

# First-publication years (source: bradleyboehmke/harrypotter README).
PUBLISHED_YEAR: dict[Book, int] = {Book.BOOK_3: 1999, Book.BOOK_4: 2000, Book.BOOK_7: 2007}

# How far into the text the title is searched for (it sits at the start of the file).
TITLE_SEARCH_CHARS = 300

# Provenance of the text and of the toc snapshot — keep in step with DATA_SOURCES.md.
TOC_SNAPSHOT_SOURCE = ("HP_Chapters.csv from "
                       "github.com/sharanyavb/harry-potter@57acafc1a9e5ed3f7c89a0d19f69d32806afbde9"
                       " (fan-compiled, US edition titles)")
PROVENANCE = Provenance(
    source_type="community",
    origin="www.readbooksvampire.com (site no longer exists), via R package",
    acquired_from="github.com/bradleyboehmke/harrypotter",
    extraction_script="scripts/pipelines/extract_hp_corpus.py",
    extraction_commit=EXTRACTION_COMMIT,
)


class Problem(NamedTuple):
    """One failed check. chapter is None for book- or corpus-level problems."""
    book: Book | None
    chapter: int | None
    message: str


# --- block 1: table of contents --------------------------------------------------------
def load_toc(path: Path, books: list[Book]) -> tuple[dict[Book, dict[int, str]], list[Problem]]:
    """Read the toc snapshot → {book: {chapter number: title}}; numbers must run 1..N."""
    problems: list[Problem] = []
    if not path.is_file():
        return {}, [Problem(None, None, f"toc snapshot not found: {path}")]

    df = pd.read_csv(path)
    toc: dict[Book, dict[int, str]] = {}
    for book in books:
        number = TOC_BOOK_NUMBER.get(book)
        if number is None:
            problems.append(Problem(book, None, "no toc book number mapping (TOC_BOOK_NUMBER)"))
            continue
        rows = df[df["Book Number"] == number].sort_values("Chapters in Book")
        if rows.empty:
            problems.append(Problem(book, None, f"book number {number} not in toc snapshot"))
            continue
        nums = [int(n) for n in rows["Chapters in Book"]]
        if nums != list(range(1, len(nums) + 1)):
            problems.append(Problem(book, None, f"toc chapter numbers not 1..N: {nums}"))
            continue
        toc[book] = dict(zip(nums, rows["Chapter Title"].astype(str).str.strip()))
    return toc, problems


# --- block 2: title comparison -------------------------------------------------------
_QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalise_title(s: str) -> str:
    """Comparison form: unicode-normalised, straight quotes, lower case, letters/digits only."""
    s = unicodedata.normalize("NFKC", s).translate(_QUOTES).casefold()
    s = re.sub(r"[^\w\s]", "", s)          # drop punctuation: "Dobby’s" == "Dobby's" == "Dobbys"
    return re.sub(r"\s+", " ", s).strip()

def title_matches(text: str, title: str) -> bool:
    """True if the (normalised) title appears near the start of the (normalised) text."""
    return normalise_title(title) in normalise_title(text[:TITLE_SEARCH_CHARS])

# --- block 3: one chapter ------------------------------------------------------------
def chapter_filename(book: Book, number: int) -> str:
    """File name produced by extract_hp_corpus: <book value>chapter_<n>.txt."""
    return f"{book.value}chapter_{number:02d}.txt"


def profile_chapter(book: Book, number: int, title: str,
                    corpus_root: Path) -> tuple[ChapterSchema | None, list[Problem]]:
    """Run the chapter checks in order (cheapest first); build the record only if all pass."""
    filename = chapter_filename(book, number)
    path = corpus_root / filename
    if not path.is_file():
        return None, [Problem(book, number, f"file missing: {filename}")]

    raw = path.read_bytes()
    if not raw.strip():
        return None, [Problem(book, number, f"file empty: {filename}")]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as err:
        return None, [Problem(book, number, f"not valid UTF-8 ({err.reason} at byte {err.start})")]

    has_title = TITLE_IN_TEXT[book]
    exception = TITLE_EXCEPTIONS.get((book, number))
    if exception:
        title = exception[0]           # reviewed: record the verified title, skip the comparison
    elif has_title and not title_matches(text, title):
        start = " ".join(text[:80].split())
        return None, [Problem(book,
                              number,
                              f"title mismatch: expected {title!r}, file starts {start!r}")]

    record = ChapterSchema(
        title=title, title_in_text=has_title, number=number, filename=filename,
        character_count=len(text), word_count=len(text.split()),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    return record, []


# --- block 4: one book ---------------------------------------------------------------
_CHAPTER_FILE = re.compile(r"^(?P<prefix>.+_)chapter_(?P<num>\d+)\.txt$")


def find_unexpected_files(book: Book, expected: set[int], corpus_root: Path) -> list[Problem]:
    """Files for this book that are not one of its expected chapters."""
    expected_names = {chapter_filename(book, n) for n in expected}
    problems = []
    for path in sorted(corpus_root.glob(f"{book.value}chapter_*.txt")):
        if path.name not in expected_names:
            problems.append(Problem(book, None, f"unexpected file: {path.name}"))
    return problems


def profile_book(book: Book, titles: dict[int, str], corpus_root: Path,
                 evidence: ProfileEvidence) -> tuple[BookSchema | None, list[Problem]]:
    """Profile every expected chapter; build the BookSchema only after the loop."""
    problems: list[Problem] = []
    chapters: dict[int, ChapterSchema] = {}
    for number, title in titles.items():
        record, chapter_problems = profile_chapter(book, number, title, corpus_root)
        problems.extend(chapter_problems)
        if record is not None:
            chapters[number] = record

    problems.extend(find_unexpected_files(book, set(titles), corpus_root))
    if len(chapters) != len(titles):
        problems.append(Problem(book, None,
                                f"{len(chapters)} of {len(titles)} expected chapters profiled"))
    if problems:
        return None, problems

    return BookSchema(
        name=book, expected_chapters=len(titles), published_year=PUBLISHED_YEAR[book],
        isbn=None, evidence=evidence, fidelity_sample=None, chapters=chapters,
    ), []


# --- block 5: whole corpus, gate, write ------------------------------------------------
def warn_if_uncommitted() -> None:
    """Warn if scripts/corpus has uncommitted changes (the record would cite older code)."""
    changes = subprocess.run(["git", "status", "--porcelain", "--", "scripts/corpus"],
                             capture_output=True, text=True, check=True).stdout.strip()
    if changes:
        print("WARNING: scripts/corpus has uncommitted changes. The record will cite the last "
              "commit, not this code. Commit first, then re-profile.")
        
def git_commit() -> str:
    """Current repo commit (for evidence.source), or 'unknown' outside a git checkout."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def profile_corpus(corpus_root: Path, books: list[Book],
                   toc_path: Path | None = None) -> tuple[CorpusSchema | None, list[Problem]]:
    """Profile all selected books. Returns (record, []) on success or (None, problems)."""
    toc, problems = load_toc(toc_path or corpus_root / TOC_RELATIVE_PATH, books)
    content: dict[Book, BookSchema] = {}
    source = f"qualify_corpus.py@{git_commit()}"
    for book in books:
        if book not in toc:
            continue                      # its toc problem is already recorded
        evidence = ProfileEvidence(source=source, notes=book_notes(book))
        record, book_problems = profile_book(book, toc[book], corpus_root, evidence)
        problems.extend(book_problems)
        if record is not None:
            content[book] = record

    if problems:
        return None, problems

    record = CorpusSchema(
        schema_version=SCHEMA_VERSION, corpus_id=compute_corpus_id(content), status="profiled",
        provenance=PROVENANCE, corpus_root=corpus_root.as_posix(),
        scope=f"Harry Potter books: {', '.join(b.value.rstrip('_') for b in books)}",
        content=content,
    )
    return record, []


def format_problems(problems: list[Problem]) -> str:
    """Problems grouped by book, chapter-level first."""
    grouped: dict[str, list[Problem]] = defaultdict(list)
    for p in problems:
        grouped[p.book.value.rstrip("_") if p.book else "corpus"].append(p)
    lines = [f"Profiling FAILED — {len(problems)} problem(s); no record written."]
    for group, items in grouped.items():
        lines.append(f"\n{group}:")
        for p in sorted(items, key=lambda p: (p.chapter is None, p.chapter or 0)):
            where = f"ch {p.chapter:>2}" if p.chapter is not None else "book "
            lines.append(f"  {where}  {p.message}")
    return "\n".join(lines)


def write_record(record: CorpusSchema, path: Path) -> str:
    """Apply the overwrite rule; return a one-line description of what happened."""
    existing: CorpusSchema | None = None
    if path.is_file():
        try:
            existing = CorpusSchema.model_validate_json(path.read_text(encoding="utf-8"))
        except ValidationError:
            existing = None               # unreadable / older format → replace (DVC keeps it)

    if existing and existing.status == "certified" and existing.corpus_id == record.corpus_id:
        return f"unchanged: corpus {record.corpus_id} already certified — nothing written"

    if existing and existing.corpus_id != record.corpus_id:
        cleared = " — CERTIFICATION CLEARED (data changed)" if existing.status == "certified" else ""
        note = f"replaced: corpus {existing.corpus_id} → {record.corpus_id}{cleared}"
    elif path.is_file():
        note = f"replaced: corpus {record.corpus_id} (profiled)"
    else:
        note = f"written: corpus {record.corpus_id} (profiled)"

    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return note


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Exit 0 = record written or unchanged; 1 = problems found."""
    parser = argparse.ArgumentParser(description="Profile the corpus and write the corpus record.")
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--toc", type=Path, default=None,
                        help=f"toc snapshot (default: <corpus-root>/{TOC_RELATIVE_PATH})")
    parser.add_argument("--books", nargs="+", choices=[b.name for b in Book],
                        default=[b.name for b in TOC_BOOK_NUMBER])
    parser.add_argument("--dry-run", action="store_true", help="run all checks, never write")
    args = parser.parse_args(argv)

    books = [Book[name] for name in args.books]
    record, problems = profile_corpus(args.corpus_root, books, args.toc)
    if problems:
        print(format_problems(problems))
        return 1

    assert record is not None
    chapters = sum(len(b.chapters) for b in record.content.values()) # pylint: disable=no-member  # pydantic field, FieldInfo false positive
    print(f"Profiling passed: {len(record.content)} book(s), {chapters} chapters, "
          f"corpus_id {record.corpus_id}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    warn_if_uncommitted()
    path = record_path(args.corpus_root)
    print(write_record(record, path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
