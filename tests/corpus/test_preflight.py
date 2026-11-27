"""
Unit tests for scripts/corpus/preflight.py.

Each test starts from a small certified corpus built in tmp_path (real chapter files,
their real sha256, evidence files bound by hash), then spoils one thing and checks that
preflight refuses with the right message — or, untouched, passes and returns what the
run needs (corpus_id + chapter hashes).
"""
# pylint: disable=missing-function-docstring   # test names describe the check
# pylint: disable=redefined-outer-name         # pytest fixtures are injected by parameter name
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.constants import Book
from scripts.corpus.corpus_models import (BookSchema, ChapterSchema, CorpusSchema,
                                          FidelitySample, ProfileEvidence, Provenance,
                                          bytes_sha256, compute_corpus_id, hash_evidence,
                                          record_path)
from scripts.corpus.preflight import PreflightResult, describe_change, run_preflight

# book -> chapter texts (chapter n = list position + 1); distinct text per chapter
TEXTS = {
    Book.BOOK_3: ["Owl post text. " * 20, "Aunt Marge text. " * 30, "Knight bus text. " * 25],
    Book.BOOK_7: ["Dark lord text. " * 22, "In memoriam text. " * 18],
}


def filename(book: Book, n: int) -> str:
    return f"{book.value}chapter_{n:02d}.txt"


# --- fixture: a certified corpus on disk -------------------------------------------------
def write_certified_corpus(root: Path) -> CorpusSchema:
    """Chapter files + evidence files + a certified record whose hashes match them."""
    content = {}
    for book, texts in TEXTS.items():
        chapters = {}
        for n, text in enumerate(texts, start=1):
            name = filename(book, n)
            raw = text.encode("utf-8")
            (root / name).write_bytes(raw)
            chapters[n] = ChapterSchema(title=f"Ch {n}", title_in_text=False, number=n,
                                        filename=name, character_count=len(text),
                                        word_count=len(text.split()), sha256=bytes_sha256(raw))
        sample = FidelitySample(chapters=[1], sampling_strategy="test", check_scope="test",
                                reference="test", result="pass", date_checked=date(2026, 11, 26))
        content[book] = BookSchema(name=book, expected_chapters=len(chapters),
                                   published_year=1999, evidence=ProfileEvidence(source="test"),
                                   fidelity_sample=sample, chapters=chapters)

    evidence_dir = root / "fidelity_evidence"
    evidence_dir.mkdir()
    evidence = [evidence_dir / "review.csv", evidence_dir / "references.json"]
    evidence[0].write_text("corpus_id,book,chapter\n", encoding="utf-8")
    evidence[1].write_text('{"references": {}}', encoding="utf-8")

    record = CorpusSchema(
        schema_version="0.1", corpus_id=compute_corpus_id(content), status="certified",
        provenance=Provenance(source_type="community", origin="test", acquired_from="test",
                              extraction_script="test"),
        certification_method="manual_review", date_certified=date(2026, 11, 26),
        evidence_files=hash_evidence(root, evidence),
        corpus_root="data/06_books", scope="test", content=content)
    record_path(root).write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return record


@pytest.fixture
def corpus(tmp_path):
    """(root, record, every chapter path) for a certified corpus in tmp_path."""
    record = write_certified_corpus(tmp_path)
    paths = sorted(tmp_path / filename(b, n) for b, texts in TEXTS.items()
                   for n in range(1, len(texts) + 1))
    return tmp_path, record, paths


def refusal(root: Path, paths: list[Path]) -> str:
    """Run preflight expecting a refusal; return the message."""
    with pytest.raises(ValueError, match="Preflight refused the run") as exc:
        run_preflight(root, paths)
    return str(exc.value)


# --- pass ---------------------------------------------------------------------------------
def test_certified_corpus_passes_with_corpus_id(corpus):
    root, record, paths = corpus
    result = run_preflight(root, paths)
    assert isinstance(result, PreflightResult)
    assert result.corpus_id == record.corpus_id


def test_result_maps_each_verified_file_to_its_certified_hash(corpus):
    root, record, paths = corpus
    result = run_preflight(root, paths)
    expected = {ch.filename: ch.sha256
                for book in record.content.values() for ch in book.chapters.values()}
    assert result.chapter_sha256 == expected


def test_scoped_run_checks_and_returns_only_its_chapters(corpus):
    root, _, _ = corpus
    paths = [root / filename(Book.BOOK_3, 2)]
    assert set(run_preflight(root, paths).chapter_sha256) == {filename(Book.BOOK_3, 2)}


def test_change_outside_the_run_does_not_block_it(corpus):
    # scoped by design: a chapter this run doesn't read is not its concern
    root, _, _ = corpus
    (root / filename(Book.BOOK_7, 1)).write_text("edited", encoding="utf-8")
    assert run_preflight(root, [root / filename(Book.BOOK_3, 1)]).chapter_sha256


def test_result_is_read_only(corpus):
    root, _, paths = corpus
    result = run_preflight(root, paths)
    with pytest.raises(ValidationError):
        result.corpus_id = "other"


# --- record: missing, invalid, not certified ------------------------------------------------
def test_missing_record_refuses(corpus):
    root, _, paths = corpus
    record_path(root).unlink()
    message = refusal(root, paths)
    assert "not found" in message and "corpus_record.json" in message


def test_invalid_record_refuses(corpus):
    root, _, paths = corpus
    record_path(root).write_text("{not json", encoding="utf-8")
    assert "invalid" in refusal(root, paths)


def test_profiled_record_refuses(corpus):
    root, record, paths = corpus
    profiled = record.model_dump()
    profiled.update(status="profiled", certification_method=None, date_certified=None,
                    evidence_files={})
    for book in profiled["content"].values():
        book["fidelity_sample"] = None
    record_path(root).write_text(CorpusSchema.model_validate(profiled).model_dump_json(),
                                 encoding="utf-8")
    assert "'profiled'" in refusal(root, paths)


# --- evidence: stop before checking chapters -------------------------------------------------
def test_edited_evidence_refuses(corpus):
    root, _, paths = corpus
    (root / "fidelity_evidence" / "review.csv").write_text("edited", encoding="utf-8")
    message = refusal(root, paths)
    assert "evidence file missing or edited" in message and "review.csv" in message


def test_missing_evidence_refuses(corpus):
    root, _, paths = corpus
    (root / "fidelity_evidence" / "references.json").unlink()
    assert "references.json" in refusal(root, paths)


def test_evidence_failure_stops_before_chapter_checks(corpus):
    root, _, paths = corpus
    (root / "fidelity_evidence" / "review.csv").write_text("edited", encoding="utf-8")
    (root / filename(Book.BOOK_3, 1)).write_text("edited", encoding="utf-8")
    assert "changed since certification" not in refusal(root, paths)


# --- chapters ---------------------------------------------------------------------------------
def test_no_chapters_refuses(corpus):
    root, _, _ = corpus
    assert "chapter files not provided" in refusal(root, [])


def test_file_not_in_record_refuses(corpus):
    root, _, paths = corpus
    stray = root / (filename(Book.BOOK_3, 1) + ".bak")
    stray.write_text("copy", encoding="utf-8")
    assert f"{stray.name}: not in the certified corpus record" in refusal(root, paths + [stray])


def test_missing_chapter_file_refuses(corpus):
    root, _, paths = corpus
    (root / filename(Book.BOOK_7, 2)).unlink()
    assert f"{filename(Book.BOOK_7, 2)}: file missing" in refusal(root, paths)


def test_edited_chapter_refuses_with_diagnosis(corpus):
    root, _, paths = corpus
    name = filename(Book.BOOK_3, 2)
    (root / name).write_text("", encoding="utf-8")
    message = refusal(root, paths)
    assert f"{name}: changed since certification" in message and "emptied" in message


def test_every_bad_chapter_reported_together(corpus):
    root, _, paths = corpus
    for n in (1, 3):
        (root / filename(Book.BOOK_3, n)).write_text("edited", encoding="utf-8")
    message = refusal(root, paths)
    assert "2 problem(s)" in message
    assert filename(Book.BOOK_3, 1) in message and filename(Book.BOOK_3, 3) in message


# --- describe_change (diagnosis only) ---------------------------------------------------------
CHAPTER = ChapterSchema(title="t", title_in_text=False, number=1, filename="f.txt",
                        character_count=10, word_count=2, sha256="0" * 64)


@pytest.mark.parametrize("raw, how", [
    (b"", "emptied"),
    (b"short", "shorter"),
    (b"a much longer text now", "longer"),
    (b"abcde fghi", "same length: edited in place"),
    (b"\xff\xfe\x00", "no longer valid UTF-8"),
])
def test_describe_change_explains_how(raw, how):
    assert how in describe_change(raw, CHAPTER)
    