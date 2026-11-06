"""
Project: SVE (ref implementation: Harry Potter Trivia)
Phase 2: Content Generation (Corpus validation before generation pipeline)

corpus_models — the corpus record contract (core data integrity for SVE).
======================================================================

Defines the certified corpus record written by certify_corpus (job 1) and read by
preflight (job 2) within the content generation pipeline.

Purpose
SVE verifies answers against the source text, so the corpus is the system's ground
truth: every later stage (generation, enrichment, validation, runtime) assumes it is
correct. Validation checks questions against this same corpus, so it cannot detect a
wrong corpus. This module defines the record that closes that gap.

Trust model (ADR-P2-026: corpus trust boundary)
- Certify once: certify_corpus (job 1) profiles every chapter deterministically,
  records the evidence, and marks the corpus `certified` after a stratified fidelity
  sample passes against a reference copy. Establishes correctness.
- Verify every run: preflight (job 2) checks the selected chapters against this
  record before any API call: files present, chapter count, sha256. Any mismatch stops
  the run. Establishes integrity (a checksum proves "unchanged", not "correct").

Contract
CorpusSchema → BookSchema (keyed by Book enum) → ChapterSchema (keyed by 1-based
chapter number). Evidence is recorded per book: each book is accepted on its own
fidelity sample (see FidelitySample). Validators enforce: certified ⇒ every book has
a passing sample; chapter keys match chapter numbers; corpus_id matches the chapter
checksums; unknown fields rejected.  

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
- Extra validation (free source only): the stratified fidelity sample against a
  reference copy, manual profiling evidence (word-count checks, outlier review),
  title-alignment checks, and "unconfirmed" provenance fields (edition, ISBN).

"""
import hashlib
from datetime import date
from typing import Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.constants import Book

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
    """How this book's deterministic profile was produced and reviewed."""
    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        ..., description=("Where the profile came from: notebook path (manual) or"
                          " 'certify_corpus.py@<commit>' (script)."))
    outliers_reviewed: list[int] = Field(
        default_factory=list, description="Short chapters reviewed and accepted as legitimate.")
    notes: str | None = Field(
        default=None, description="Free-text notes, e.g. 'titles absent from text (book 7)'.")

# Chapter fidelity (stratified sample of chapters from same book, compared to a reference copy)
class FidelitySample(BaseModel):
    """
    Fidelity sample result for ONE book.

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
    sha256: str = Field(
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
            unknown = sorted(set(self.fidelity_sample.chapters) - set(self.chapters))
            if unknown:
                raise ValueError(
                    f"fidelity sample lists chapters not in {self.name.value}: {unknown}")
        return self

    @model_validator(mode="after")
    def keys_match_numbers(self) -> Self:
        """Validate that chapter keys match chapter.number."""
        bad = [k for k, ch in self.chapters.items() if k != ch.number]
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
    corpus_id : str = Field(
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
    content: dict[Book, BookSchema] = Field(..., description="Books keyed by Book enum value.")

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
            unsampled = [b.value for b, rec in self.content.items()
                         if rec.fidelity_sample is None or rec.fidelity_sample.result != "pass"]
            if missing or unsampled:
                raise ValueError(
                    "status=certified requires certification_method + date_certified "
                    f"(missing: {missing}) and a passing fidelity sample for every book "
                    f"(missing/failed: {unsampled})")
        return self
