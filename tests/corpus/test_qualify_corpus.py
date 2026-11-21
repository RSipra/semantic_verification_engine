"""Unit tests for scripts/corpus/qualify_corpus.py (job 1: profile the corpus).

Each test builds a tiny fake corpus in a temporary folder: a toc snapshot with two
chapters per book and matching chapter files. Book 3 files start with their title;
book 7 files don't (TITLE_IN_TEXT).
"""
# pylint: disable=redefined-outer-name   # pytest fixtures are injected by parameter name
# pylint: disable=missing-function-docstring   # test names describe the check
import json
from datetime import date

import pytest

from core.constants import Book
from scripts.corpus import qualify_corpus as qc
from scripts.corpus.corpus_models import CorpusSchema, FidelitySample, record_path

BOOKS = [Book.BOOK_3, Book.BOOK_7]
TITLES = {
    Book.BOOK_3: {1: "Owl Post", 2: "Dobby’s Warning"},      # curly apostrophe, as in the snapshot
    Book.BOOK_7: {1: "The Dark Lord Ascending", 2: "In Memoriam"},
}


def write_toc(root, titles=TITLES):
    rows = ["Book,Book Number,Chapters Overall,Chapters in Book,Chapter Key,"
            "Chapter Title,Page Start,Page End"]
    for book, chapters in titles.items():
        number = qc.TOC_BOOK_NUMBER[book]
        for n, title in chapters.items():
            rows.append(f"Book {number},{number},0,{n},{number}.{n:02d},\"{title}\",1,2")
    path = root / qc.TOC_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_chapter(root, book, n, body=None):
    if body is None:
        title = TITLES[book][n].replace("’", "'").upper()        # files use straight quotes, caps
        body = (f"{title}\n\n" if qc.TITLE_IN_TEXT[book] else "") + f"Chapter text {n} for {book.name}."
    (root / qc.chapter_filename(book, n)).write_text(body, encoding="utf-8")


@pytest.fixture
def corpus(tmp_path):
    write_toc(tmp_path)
    for book, chapters in TITLES.items():
        for n in chapters:
            write_chapter(tmp_path, book, n)
    return tmp_path


def run(root, *extra):
    return qc.main(["--corpus-root", str(root), "--books", *[b.name for b in BOOKS], *extra])


# --- titles --------------------------------------------------------------------------
def test_curly_and_straight_apostrophes_match():
    assert qc.title_matches("DOBBY'S WARNING\n\nText", "Dobby’s Warning")


def test_title_must_be_near_the_start():
    text = "x" * qc.TITLE_SEARCH_CHARS + "OWL POST"
    assert not qc.title_matches(text, "Owl Post")


# --- happy path ----------------------------------------------------------------------
def test_clean_corpus_writes_profiled_record(corpus):
    assert run(corpus) == 0
    record = CorpusSchema.model_validate_json(record_path(corpus).read_text())
    assert record.status == "profiled"
    assert set(record.content) == set(BOOKS)
    assert record.content[Book.BOOK_3].chapters[2].title_in_text is True
    assert record.content[Book.BOOK_7].chapters[1].title_in_text is False


def test_dry_run_writes_nothing(corpus):
    assert run(corpus, "--dry-run") == 0
    assert not record_path(corpus).exists()


def test_book_without_titles_skips_title_check(corpus):
    write_chapter(corpus, Book.BOOK_7, 1, body="No title here at all.")
    assert run(corpus) == 0


# --- go/no-go: any problem → nothing written ---------------------------------------
@pytest.mark.parametrize("damage, expected", [
    (lambda r: (r / qc.chapter_filename(Book.BOOK_3, 2)).unlink(), "file missing"),
    (lambda r: write_chapter(r, Book.BOOK_3, 2, body="   \n"), "file empty"),
    (lambda r: (r / qc.chapter_filename(Book.BOOK_3, 2)).write_bytes(b"\xff\xfe bad"), "not valid UTF-8"),
    (lambda r: write_chapter(r, Book.BOOK_3, 2, body="THE WRONG TITLE\n\ntext"), "title mismatch"),
    (lambda r: write_chapter(r, Book.BOOK_3, 9, body="OWL POST\n\ntext"), "unexpected file"),
    (lambda r: write_toc(r, {**TITLES, Book.BOOK_3: {1: "Owl Post", 3: "Gap"}}), "not 1..N"),
    (lambda r: (r / qc.TOC_RELATIVE_PATH).unlink(), "toc snapshot not found"),
])
def test_problem_blocks_the_write(corpus, capsys, damage, expected):
    damage(corpus)
    assert run(corpus) == 1
    assert expected in capsys.readouterr().out
    assert not record_path(corpus).exists()


def test_all_problems_reported_in_one_pass(corpus, capsys):
    (corpus / qc.chapter_filename(Book.BOOK_3, 1)).unlink()
    write_chapter(corpus, Book.BOOK_7, 2, body="")
    assert run(corpus) == 1
    out = capsys.readouterr().out
    assert "prisoner_of_azkaban" in out and "deathly_hallows" in out


# --- overwrite rule ------------------------------------------------------------------
def certify(path):
    """Simulate a later certification of the record at path."""
    data = json.loads(path.read_text())
    sample = FidelitySample(chapters=[1], sampling_strategy="test", check_scope="test",
                            reference="test", result="pass", date_checked=date(2026, 11, 9))
    for book in data["content"].values():
        book["fidelity_sample"] = json.loads(sample.model_dump_json())
    data.update(status="certified", certification_method="manual_review", 
                date_certified="2026-11-09",
                evidence_files={"fidelity_evidence/e.csv": "a" * 64})
    path.write_text(CorpusSchema.model_validate(data).model_dump_json(indent=2))


def test_certified_unchanged_corpus_is_not_overwritten(corpus, capsys):
    run(corpus)
    certify(record_path(corpus))
    assert run(corpus) == 0
    assert "already certified" in capsys.readouterr().out
    assert CorpusSchema.model_validate_json(record_path(corpus).read_text()).status == "certified"


def test_changed_data_clears_certification(corpus, capsys):
    run(corpus)
    certify(record_path(corpus))
    write_chapter(corpus, Book.BOOK_7, 2, body="Edited text.")
    assert run(corpus) == 0
    assert "CERTIFICATION CLEARED" in capsys.readouterr().out
    assert CorpusSchema.model_validate_json(record_path(corpus).read_text()).status == "profiled"
