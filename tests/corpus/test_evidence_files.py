"""
Tests for certification evidence binding (corpus_models).

evidence_files maps each evidence file (path relative to corpus_root) to the sha256 of its
bytes. promote writes it; preflight re-checks it with changed_evidence.
"""
# pylint: disable=missing-function-docstring   # test names describe the check
# pylint: disable=redefined-outer-name         # pytest fixtures are injected by parameter name
from datetime import date
import hashlib

import pytest
from pydantic import ValidationError

from scripts.corpus.corpus_models import (CorpusSchema, FidelitySample, changed_evidence,
                                          file_sha256, hash_evidence)

HASH = "a" * 64


def certify(rec: CorpusSchema, evidence_files: dict[str, str]) -> CorpusSchema:
    """Return rec as a certified record with a passing sample per book."""
    data = rec.model_dump()
    for book in data["content"].values():
        book["fidelity_sample"] = FidelitySample(
            chapters=[1], sampling_strategy="test", check_scope="test", reference="test",
            result="pass", date_checked=date(2026, 11, 20)).model_dump()
    data.update(status="certified", certification_method="manual_review",
                date_certified=date(2026, 11, 20), evidence_files=evidence_files)
    return CorpusSchema.model_validate(data)


@pytest.fixture
def evidence(tmp_path):
    """Two evidence files under tmp_path/fidelity_evidence."""
    folder = tmp_path / "fidelity_evidence"
    folder.mkdir()
    csv = folder / "fidelity_evidence_x.csv"
    refs = folder / "fidelity_references_x.json"
    csv.write_bytes(b"a,b\n1,2\n")
    refs.write_bytes(b'{"k": "v"}')
    return [csv, refs]


# --- file_sha256 / hash_evidence ----------------------------------------------------------
def test_file_sha256_hashes_exact_bytes(tmp_path):
    path = tmp_path / "f.txt"
    path.write_bytes(b"line\r\n")
    assert file_sha256(path) == hashlib.sha256(b"line\r\n").hexdigest()


def test_hash_evidence_keys_are_relative_posix_paths(tmp_path, evidence):
    hashes = hash_evidence(tmp_path, evidence)
    assert set(hashes) == {"fidelity_evidence/fidelity_evidence_x.csv",
                           "fidelity_evidence/fidelity_references_x.json"}


def test_hash_evidence_rejects_file_outside_corpus_root(tmp_path):
    outside = tmp_path.parent / "elsewhere.csv"
    with pytest.raises(ValueError):
        hash_evidence(tmp_path / "root", [outside])


# --- changed_evidence ----------------------------------------------------------------------
def test_unchanged_evidence_reports_nothing(tmp_path, evidence):
    assert changed_evidence(tmp_path, hash_evidence(tmp_path, evidence)) == []


def test_edited_file_is_reported(tmp_path, evidence):
    hashes = hash_evidence(tmp_path, evidence)
    evidence[0].write_bytes(b"a,b\n1,3\n")
    assert changed_evidence(tmp_path, hashes) == ["fidelity_evidence/fidelity_evidence_x.csv"]


def test_missing_file_is_reported(tmp_path, evidence):
    hashes = hash_evidence(tmp_path, evidence)
    evidence[1].unlink()
    assert changed_evidence(tmp_path, hashes) == ["fidelity_evidence/fidelity_references_x.json"]


# --- CorpusSchema.evidence_files ------------------------------------------------------------
def test_profiled_record_defaults_to_no_evidence(record):
    assert record.evidence_files == {}


def test_certified_without_evidence_files_rejected(record):
    with pytest.raises(ValidationError, match="evidence_files"):
        certify(record, {})


def test_certified_with_evidence_files_accepted(record):
    rec = certify(record, {"fidelity_evidence/e.csv": HASH})
    assert rec.evidence_files == {"fidelity_evidence/e.csv": HASH}


@pytest.mark.parametrize("path", ["/abs/e.csv", "../outside/e.csv", "fidelity_evidence/../../e.csv"])
def test_path_escaping_corpus_root_rejected(record, path):
    with pytest.raises(ValidationError, match="relative inside corpus_root"):
        certify(record, {path: HASH})


@pytest.mark.parametrize("bad_hash", ["abc", "A" * 64, "g" * 64])
def test_malformed_hash_rejected(record, bad_hash):
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        certify(record, {"fidelity_evidence/e.csv": bad_hash})
