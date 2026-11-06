"""Unit tests for the corpus record contract (scripts/pipelines/corpus/corpus_models.py).

Each test proves one rule of the contract, in both directions: valid records are
accepted, and each validator refuses what it should.
"""
# pylint: disable=redefined-outer-name   # pytest fixtures are injected by parameter name
# pylint: disable=missing-function-docstring   # test names describe the check

from datetime import date

import pytest
from pydantic import ValidationError

from core.constants import Book
from scripts.corpus.corpus_models import (BookSchema, ChapterSchema, CorpusSchema,
                                          FidelitySample, ProfileEvidence,Provenance,
                                          compute_corpus_id)


# --- builders ---------------------------------------------------------------
def make_chapter(n: int) -> ChapterSchema:
    return ChapterSchema(title=f"Ch {n}", title_in_text=True, number=n,
                         filename=f"prisoner_of_azkaban_chapter_{n}.txt",
                         character_count=100, word_count=20, sha256=f"{n:064x}")


def make_book(sample: FidelitySample | None = None) -> BookSchema:
    return BookSchema(name=Book.BOOK_3, expected_chapters=22, published_year=1999, isbn=None,
                      evidence=ProfileEvidence(source="notebooks/eda.ipynb"),
                      fidelity_sample=sample, chapters={1: make_chapter(1), 2: make_chapter(2)})


def make_corpus(content: dict, **overrides) -> CorpusSchema:
    fields = {
        "schema_version": "0.1",
        "corpus_id": compute_corpus_id(content),
        "status": "profiled",
        "provenance": Provenance(source_type="community", 
                                 origin="readbooksvampire.com via R package",
                                 acquired_from="github.com/bradleyboehmke/harrypotter",
                                 extraction_script="scripts/pipelines/extract_hp_corpus.py"),
        "corpus_root": "data/06_books",
        "scope": "HP books 3, 4, 7",
        "content": content
    }
    return CorpusSchema(**{**fields, **overrides})


# --- fixtures ---------------------------------------------------------------
@pytest.fixture
def passing_sample() -> FidelitySample:
    return FidelitySample(chapters=[1, 2], sampling_strategy="stratified: first, last",
                          check_scope="start/mid/end passages", reference="owned print copy",
                          result="pass", date_checked=date(2026, 11, 5))


@pytest.fixture
def profiled_content() -> dict:
    return {Book.BOOK_3: make_book()}


# --- accepted ---------------------------------------------------------------
def test_profiled_record_is_valid(profiled_content):
    assert make_corpus(profiled_content).status == "profiled"


def test_certified_record_with_evidence_is_valid(passing_sample):
    content = {Book.BOOK_3: make_book(sample=passing_sample)}
    record = make_corpus(content, status="certified", certification_method="manual_review",
                         date_certified=date(2026, 11, 5))
    assert record.status == "certified"


def test_corpus_id_is_deterministic(profiled_content):
    assert compute_corpus_id(profiled_content) == compute_corpus_id(profiled_content)


def test_corpus_id_changes_when_data_changes(profiled_content):
    changed_ch2 = make_chapter(2).model_copy(update={"sha256": "f" * 64})
    changed = {Book.BOOK_3: make_book().model_copy(
        update={"chapters": {1: make_chapter(1), 2: changed_ch2}})}
    assert compute_corpus_id(changed) != compute_corpus_id(profiled_content)


# --- refused ----------------------------------------------------------------
def test_certified_without_evidence_is_refused(profiled_content):
    with pytest.raises(ValidationError, match="certified requires"):
        make_corpus(profiled_content, status="certified")


def test_certified_with_failed_sample_is_refused(passing_sample):
    failed = passing_sample.model_copy(update={"result": "fail"})
    content = {Book.BOOK_3: make_book(sample=failed)}
    with pytest.raises(ValidationError, match="certified requires"):
        make_corpus(content, status="certified", certification_method="manual_review",
                    date_certified=date(2026, 11, 5))


def test_wrong_corpus_id_is_refused(profiled_content):
    with pytest.raises(ValidationError, match="does not match content"):
        make_corpus(profiled_content, corpus_id="0" * 16)


def test_unknown_sampled_chapter_is_refused(passing_sample):
    with pytest.raises(ValidationError, match="not in"):
        make_book(sample=passing_sample.model_copy(update={"chapters": [1, 99]}))


def test_chapter_key_number_mismatch_is_refused():
    with pytest.raises(ValidationError, match="do not match chapter.number"):
        BookSchema(**{**make_book().model_dump(), "chapters": {1: make_chapter(2)}})


@pytest.mark.parametrize("override", [
    {"foo": 1},                    # unknown field (extra="forbid")
    {"schema_version": "0.2"},     # unknown record version
    {"status": "approved"},        # not a lifecycle status
])
def test_invalid_corpus_fields_are_refused(profiled_content, override):
    with pytest.raises(ValidationError):
        make_corpus(profiled_content, **override)


def test_bad_sha256_is_refused():
    with pytest.raises(ValidationError):
        make_chapter(1).model_copy(update={"sha256": "not-a-hash"}).model_validate(
            {**make_chapter(1).model_dump(), "sha256": "not-a-hash"})
