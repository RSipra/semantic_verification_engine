"""Tests for FidelityReferences (corpus_models) and its reader (sampling)."""
import json

import pytest
from pydantic import ValidationError

from core.constants import Book
from scripts.corpus.corpus_models import FidelityReferences
from scripts.corpus.sampling import read_references, references_path

CORPUS_ID = "abc123"
REFS = {Book.BOOK_3.value: "Book 3 e-book; ISBN 978-0-00-000000-0",
        Book.BOOK_7.value: "Book 7 e-book; ISBN 978-0-00-000000-1"}


def write_refs(tmp_path, data):
    path = references_path(tmp_path, CORPUS_ID)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_valid_file_round_trips(tmp_path):
    refs = read_references(write_refs(tmp_path, {"corpus_id": CORPUS_ID, "references": REFS}))
    assert refs.corpus_id == CORPUS_ID
    assert refs.references[Book.BOOK_3] == REFS[Book.BOOK_3.value]


def test_keys_parse_to_book_enum():
    refs = FidelityReferences(corpus_id=CORPUS_ID, references=REFS)
    assert set(refs.references) == {Book.BOOK_3, Book.BOOK_7}


def test_unknown_book_rejected():
    with pytest.raises(ValidationError):
        FidelityReferences(corpus_id=CORPUS_ID, references={"book_99": "x"})


def test_empty_references_rejected():
    with pytest.raises(ValidationError):
        FidelityReferences(corpus_id=CORPUS_ID, references={})


def test_blank_reference_rejected():
    with pytest.raises(ValidationError, match="blank reference"):
        FidelityReferences(corpus_id=CORPUS_ID, references={Book.BOOK_3.value: "   "})


def test_extra_field_rejected():
    with pytest.raises(ValidationError):
        FidelityReferences(corpus_id=CORPUS_ID, references=REFS, reviewer="me")


def test_missing_corpus_id_rejected(tmp_path):
    with pytest.raises(ValidationError):
        read_references(write_refs(tmp_path, {"references": REFS}))


def test_path_sits_beside_evidence_csv(tmp_path):
    path = references_path(tmp_path, CORPUS_ID)
    assert path == tmp_path / "fidelity_evidence" / f"fidelity_references_{CORPUS_ID}.json"
