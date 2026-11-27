"""
Project: SVE (ref implementation: Harry Potter Trivia)
Phase 2: Content Generation (Corpus validation before generation pipeline)

corpus_models — the corpus record contract (core data integrity for SVE).
======================================================================

Defines the certified record: profiled by qualify_corpus, certified by `sampling promote`,
and read by preflight before every content generation run.

Purpose
--------
SVE verifies answers against the source text, so the corpus is the system's ground
truth: every later stage (generation, enrichment, validation, runtime) assumes it is
correct. Validation checks questions against this same corpus, so it cannot detect a
wrong corpus. This module defines the record that closes that gap.

Trust model (ADR-P2-026: corpus trust boundary)
- Qualify once (job 1): qualify_corpus profiles every chapter deterministically
  (status `profiled`); a person reviews a planned sample against a reference edition
  (`sampling select` / `show`); `sampling promote` marks the corpus `certified` and binds
  the review evidence by hash. Establishes correctness. Required for any pipeline run,
  trials included.
- Verify every run (job 2): preflight checks the record is certified and the selected
  chapters and evidence files still match their recorded sha256 before any API call.
  Any mismatch stops the run. Establishes integrity (a checksum proves "unchanged",
  not "correct").

Contract
---------
Record structure (one JSON file per corpus; [step] = who fills the field)
  CorpusSchema                                             corpus_record.json
  ├── schema_version, corpus_id, status, corpus_root, scope    [profile]
  ├── provenance: Provenance                                   [profile]
  ├── certification_method, date_certified, evidence_files     [promote]
  └── content: {Book -> BookSchema}
        ├── name, expected_chapters, published_year, isbn      [profile]
        ├── evidence: ProfileEvidence    how it was measured   [profile]
        ├── fidelity_sample: FidelitySample | None
        │                                whether it matched     [promote]
        └── chapters: {int -> ChapterSchema}                   [profile]
              title, title_in_text, number, filename, counts, sha256
promote never changes [profile] fields: fix those by re-profiling.              

Evidence files (outside the record, in <corpus_root>/fidelity_evidence/)
  fidelity_evidence_<corpus_id>.csv     rows of SampleReviewRow  [select; reviewer fills]
  fidelity_references_<corpus_id>.json  FidelityReferences       [reviewer]

Validators: certified => method, date, evidence_files and a passing sample for every
book; chapter keys == chapter.number; sampled chapters exist; corpus_id matches the
chapter checksums; evidence paths stay inside corpus_root; unknown fields rejected.

Workflow and specification
--------------------------- 
profile -> select -> review -> promote: docs/adrs/ADR-P2-026_specs.md
(section 1 workflow, section 6 promote, section 7 record).

Design note — why certification is required.
------------------------------------------------
The corpus is a free, community-processed text (R package sourced from a book-text
site), chosen because the project started as exploratory. A licensed, publisher-verified
copy can be adopted later; it would simplify certification, since the publisher's guarantee
would replace most of the correctness checks below. 
- Base requirement (regardless of source): the corpus record contract, per-chapter
  sha256, and preflight verification every run of the content generation pipeline. 
  Files can change after they arrive, so proving a run uses the certified text is
  always this system's job (with a licensed copy, checksums would be verified against
  the publisher's values.)
- Extra validation (free source only): the fidelity sample reviewed against a reference
  edition, title checks against an independent table of contents,
  and "unconfirmed" provenance fields (edition, ISBN).

"""
import hashlib
import json
from datetime import date
from typing import Literal, Self, TypeVar
from pathlib import Path, PurePosixPath
import re
from collections.abc import Callable

from pydantic import (BaseModel, ConfigDict, Field, model_validator,
                      field_validator, field_serializer, ValidationError)
import pandas as pd

from core.constants import Book
from core.models import CorpusId, Sha256Hex
from notebook_support import notebook_config as nb_cfg

DEFAULT_CORPUS_ROOT = nb_cfg.BOOK_TEXT
RECORD_FILENAME = "corpus_record.json"

SHA256_HEX = re.compile(r"[0-9a-f]{64}")

# Hashing: one definition (bytes_sha256), two entry points.
# - qualify_corpus already holds the raw bytes (it needs them for its empty / UTF-8 checks),
#   so it calls bytes_sha256 directly instead of reading the file twice.
# - promote / preflight start from a path, so they call file_sha256.
# Profiling and verification must hash identically, or every chapter would look "changed".
def bytes_sha256(data: bytes) -> str:
    """sha256 of raw bytes — the single hashing definition for chapters and evidence."""
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    """sha256 of the file's exact bytes (no decoding, so encoding/newline changes are detected)."""
    return bytes_sha256(path.read_bytes())


def hash_evidence(corpus_root: Path, paths: list[Path]) -> dict[str, str]:
    """Map each evidence file to its sha256, keyed by POSIX path relative to corpus_root."""
    return {p.relative_to(corpus_root).as_posix(): file_sha256(p) for p in sorted(paths)}


def changed_evidence(corpus_root: Path, evidence_files: dict[str, str]) -> list[str]:
    """Evidence files that are missing or whose bytes no longer match the recorded hash."""
    return [rel for rel, expected in sorted(evidence_files.items())
            if not (corpus_root / rel).is_file() or file_sha256(corpus_root / rel) != expected]


def record_path(corpus_root: Path) -> Path:
    """
    Where the corpus record lives (same for every corpus).
    Different corpus has a different corpus_root path
    """
    return corpus_root / RECORD_FILENAME

CorpusStatus = Literal["profiled", "certified", "superseded"]
CertificationMethod = Literal["manual_review", "script", "script+llm"]

# Provenance fields (for corpus record)
class Provenance(BaseModel):
    """Provenance information for the corpus record."""
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["community", "licensed"] = Field(
        ..., description=("community = free processed text (inspection-based trust); "
                          "licensed = publisher-verified copy."))
    origin: str = Field(
        ..., description=("Where the text originally came from, "
                          "e.g. 'readbooksvampire.com via R package' or the publisher."))
    acquired_from: str = Field(
        ..., description=("What was actually obtained, "
                          "e.g. 'github.com/bradleyboehmke/harrypotter@<commit>' "
                          "or a purchase / licence reference."))
    extraction_script: str = Field(..., description="Script that produced the chapter files.")
    extraction_commit: str | None = Field(
        default=None, description="Repo commit of the extraction script run.")

# Book level evidence (word-count check, outlier review, etc.)
class ProfileEvidence(BaseModel):
    """
    How this book's deterministic profile was produced and reviewed.
    Per book, written by qualify_corpus at profiling: how the profile was produced.
    """
    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        ..., description=("Where the profile came from: notebook path (manual) or"
                          " 'qualify_corpus.py@<commit>' (script)."))
    outliers_reviewed: list[int] = Field(
        default_factory=list, description="Short chapters reviewed and accepted as legitimate.")
    notes: str | None = Field(
        default=None, description="Free-text notes, e.g. 'titles absent from text (book 7)'.")

# Chapter fidelity (stratified sample of chapters from same book, compared to a reference copy)
class FidelitySample(BaseModel):
    """
    Fidelity sample result for ONE book.
    
    Per book, written at promotion: summary of the review rows (chapters, strategy, reference,
    result).

    Each book is accepted on its own sample: result = "pass" only if every sampled
    chapter matched the reference. The checking itself may span several books in one
    session; results are still recorded per book, so adding a book later needs only
    that book's sample.
    """
    model_config = ConfigDict(extra="forbid")

    chapters: list[int] = Field(..., min_length=1, description="Chapter numbers sampled.")
    sampling_strategy: str = Field(..., description=("How chapters were chosen, e.g. 'stratified: "
                                                     "first, last, short outliers + random'"))
    check_scope: str = Field(..., description=("What was compared per chapter, e.g. 'start, middle,"
                                               " end passages (~500 chars each)' or 'full text'."))
    reference: str = Field(..., description=("Reference the sample was compared against, "
                                             "e.g. 'owned print copy'."))
    result: Literal["pass", "fail"] = Field(..., description="Outcome of the sample check.")
    date_checked: date = Field(..., description="Date the sample was checked.")

# standardize labels for chapter selection
Labels = Literal["first", "last", "shortest", "longest", "iqr_outlier", "random"]

class SampleReviewRow(BaseModel):
    """
    One sampled chapter in the fidelity review CSV (the detailed, hand-filled evidence).

    Flow using sampling.py:
      1. select_sample writes one row per sampled chapter to
         fidelity_evidence/fidelity_evidence_<corpus_id>.csv (result and notes empty).
      2. The reviewer fills in result ("pass" / "fail") and notes for each row.
      3. The review helper reads the CSV back through this model (validated: it is
         hand-edited), applies the round rules, and — if every book passes — summarises
         each book's rows into one FidelitySample in the corpus record (status → certified).

    The CSV keeps the per-chapter detail; the record's FidelitySample keeps the per-book
    summary. Rows are valid only for the corpus_id they carry.
    """
    model_config = ConfigDict(extra="forbid")

    corpus_id: str = Field(..., description="Corpus id for which this chapter was sampled.")
    book: Book = Field(..., description="The book to which this chapter belongs.")
    chapter: int = Field(..., ge=1, description="Chapter number.")
    reason: list[Labels] = Field(...,
        min_length=1,
        description="Why this chapter was sampled. Stored in the CSV as a JSON list, "
                    'e.g. ["first", "shortest"] (converted by the two hooks below).')
    round: int = Field(
        default=1,
        ge=1, le=2,
        description="Round of review: 1 = initial, 2 = re-review after a fail.")
    result: Literal["", "pass", "fail"] = Field(
        default="",
        description="Result of the review: empty = not yet reviewed, ")
    notes: str = Field(
        default="",
        description=("Review result: '' = not yet reviewed, "
                     "'pass' or 'fail' per ADR-P2-026 criterion."))

    # CSV conversion for `reason` (a CSV cell can only hold text)
    @field_validator("reason", mode="before")
    @classmethod
    def reason_from_csv(cls, v):
        """Reading the CSV: the cell is a JSON string → parse it into a list."""
        return json.loads(v) if isinstance(v, str) else v

    @field_serializer("reason", when_used="json")
    def reason_to_csv(self, v: list[str]) -> str:
        """Writing the CSV (model_dump(mode='json')): list → JSON string for the cell."""
        return json.dumps(v)

EVIDENCE_COLS = list(SampleReviewRow.model_fields)

class ChapterSchema(BaseModel):
    """Schema for a single chapter."""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., description="Chapter title from the book's table of contents.")
    title_in_text: bool = Field(
        ..., description=("True if the file text contains the title (alignment checkable); "
                          "False if not (e.g. book 7)."))
    number: int = Field(..., ge=1, description="1-based chapter number, taken from the file name.")
    filename: str = Field(..., description="Relative path to the chapter file")
    character_count: int = Field(
        ..., ge=0, description=("len() of the decoded UTF-8 text. "
                                "Diagnoses a checksum mismatch (emptied / truncated / edited)."))
    word_count: int = Field(
        ..., ge=0, description=("len(text.split()) — fixed whitespace method. "
                                "Diagnostic, like character_count."))
    # fingerprint of file content
    sha256: Sha256Hex = Field(
        ...,
        pattern=r"^[0-9a-f]{64}$",
        description="SHA-256 of the raw file bytes. The run-time integrity check.")

class BookSchema(BaseModel):
    """Schema for a book."""
    model_config = ConfigDict(extra="forbid")

    name: Book = Field(..., description="The book enum value")
    expected_chapters: int = Field(
        ..., ge=1, description="Chapter count from table of contents: an independent reference.")
    published_year: int | Literal["unconfirmed"] = Field(
        ..., description="year of publication, or 'unconfirmed' if not verified")
    isbn: str | None = Field(
        default=None, description="ISBN number for the book, if available; can be null")
    evidence: ProfileEvidence = Field(
        ..., description="Evidence of the deterministic profile for this book")
    fidelity_sample: FidelitySample | None = Field(
        default=None, description="Sampled fidelity check; None until sampled.")
    chapters: dict[int, ChapterSchema] = Field(
        description="Chapters keyed by chapter number.")

    @model_validator(mode="after")
    def sampled_chapters_exist(self) -> Self:
        """Validate that every sampled chapter is in this book."""
        if self.fidelity_sample:
            unknown = sorted(set(self.fidelity_sample.chapters) - set(self.chapters)) # pylint: disable=no-member  # pydantic field, FieldInfo false positive
            if unknown:
                raise ValueError(
                    f"fidelity sample lists chapters not in {self.name.value}: {unknown}") # pylint: disable=no-member  # pydantic field, FieldInfo false positive
        return self

    @model_validator(mode="after")
    def keys_match_numbers(self) -> Self:
        """Validate that chapter keys match chapter.number."""
        bad = [k for k, ch in self.chapters.items() if k != ch.number] # pylint: disable=no-member  # pydantic field, FieldInfo false positive
        if bad:
            raise ValueError(f"chapter keys do not match chapter.number: {bad}")
        return self

def compute_corpus_id(content: "dict[Book, BookSchema]") -> str:
    """Deterministic corpus id: hash of every chapter checksum (book, number order)."""
    parts = [f"{book.value}:{n}:{ch.sha256}"
             for book in sorted(content, key=lambda b: b.value)
             for n, ch in sorted(content[book].chapters.items())]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]

class CorpusSchema(BaseModel):
    """Schema for the certified corpus record."""
    model_config = ConfigDict(extra="forbid")

    schema_version:  Literal["0.1"] = Field(
        ..., description=("Record format version; "
                                "preflight refuses any other value. 0.x = draft."))
    corpus_id: CorpusId = Field(
        ..., description=("Hash of all chapter checksums; "
                          "changes if and only if the corpus data changes."))
    status: CorpusStatus = Field(..., description=("profiled = deterministic profile done; "
                                                   "certified = fidelity samples passed; "
                                                   "superseded = replaced by a newer record."))
    provenance: Provenance = Field(
        ..., description="Where the text came from and how it was extracted.")
    certification_method: CertificationMethod | None = Field(
        default=None, description="How certification was done; None until certified.")
    corpus_root: str = Field(
        ..., description="root directory for the corpus. Chapter filepaths are relative to this")
    scope: str = Field(
        ..., description="scope of the corpus, e.g. HP Book Series (1-7), Canadian version (tbc)")
    date_certified: date | None = Field(
        default=None, description="Date the corpus was certified; None until certified.")
    evidence_files: dict[str, Sha256Hex] = Field(
        default_factory=dict,
        description="Certification evidence (e.g. fidelity review CSV, book reference file): "
                    "path relative to corpus_root -> sha256 of file bytes.")
    content: dict[Book, BookSchema] = Field(..., description="Books keyed by Book enum value.")

    @field_validator("evidence_files")
    @classmethod
    def evidence_files_well_formed(cls, v:dict[str,Sha256Hex]) -> dict[str, Sha256Hex]:
        """
        Check the shape of each evidence entry, not whether it matches the files on disk.

        - path: relative and inside corpus_root (no leading '/', no '..'), so preflight
          only ever hashes files inside the DVC-tracked folder.
        - hash: format enforced by the Sha256Hex type on the field, so a malformed value
+         fails at load instead of as an unexplained mismatch in preflight.

        Collects every bad entry and raises once. Matching against disk: changed_evidence.
        """
        bad_paths = [
            p for p in v if PurePosixPath(p).is_absolute() or ".." in PurePosixPath(p).parts]
        if bad_paths:
            raise ValueError(
                f"evidence_files: paths must be relative inside corpus_root {bad_paths}")
        return v

    @model_validator(mode="after")
    def corpus_id_matches_content(self) -> Self:
        """Validate that corpus_id equals the id computed from the chapter checksums."""
        expected = compute_corpus_id(self.content)
        if self.corpus_id != expected:
            raise ValueError(f"corpus_id {self.corpus_id!r} does not match content ({expected!r})")
        return self

    @model_validator(mode="after")
    def certified_has_evidence(self) -> Self:
        """Validate that certified corpus has all required evidence."""
        if self.status == "certified":
            missing = [f for f in (
                "certification_method", "date_certified")
                       if getattr(self, f) is None]
            if not self.evidence_files:
                missing.append("evidence_files")
            unsampled = [b.value for b, rec in self.content.items()  # pylint: disable=no-member  # pydantic field, FieldInfo false positive 
                         if rec.fidelity_sample is None or rec.fidelity_sample.result != "pass"]
            if missing or unsampled:
                raise ValueError(
                    "status=certified requires certification_method + date_certified + evidence_files "
                    f"(missing: {missing}) and a passing fidelity sample for every book "
                    f"(missing/failed: {unsampled})")
        return self

def read_corpus_record(corpus_root: Path) -> CorpusSchema:
    """Read and validate the corpus record in corpus_root (raises if missing or invalid)."""
    return CorpusSchema.model_validate_json(record_path(corpus_root).read_text(encoding="utf-8"))

# define placeholder for type determined at function call.
T = TypeVar('T')

def load_input(label: str, path: Path, reader: Callable[[Path], T], problems: list[str],
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

class FidelityReferences(BaseModel):
    """
    The reference edition each book was checked against in the manual fidelity review.

    Hand-written, one file per corpus, stored beside the review CSV. Validated on read:
    promote copies each value into that book's FidelitySample.reference.
    """
    model_config = ConfigDict(extra="forbid")

    corpus_id: str = Field(..., description="Corpus the review was performed on")
    references: dict[Book, str] = Field(
        ..., 
        min_length=1,
        description="Book -> reference edition (title, publisher, year, ISBN, access)"
        )

    @field_validator("references")
    @classmethod
    def no_blank_references(cls, v: dict[Book, str]) -> dict[Book, str]:
        """Ensure reference is not empty"""
        blank = [book.value for book, ref in v.items() if not ref.strip()]
        if blank:
            raise ValueError(f"blank reference for: {', '.join(blank)}")
        return v
