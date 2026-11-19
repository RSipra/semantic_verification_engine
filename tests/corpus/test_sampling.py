"""
Unit tests for scripts/corpus/sampling.py.

iqr_outliers: each test pins one behaviour of the outlier rule. The fence test uses
numbers worked out by hand (inclusive quartiles, multiplier 1.5).
select_book_sample: each test builds a small BookSchema in memory and pins one rule of
the sampling plan.
Round-1 helpers (select_corpus_sample, evidence_path, write_evidence, read_evidence):
a small two-book record; the round trip checks the review CSV reads back unchanged.
"""
# pylint: disable=missing-function-docstring   # test names describe the check
# pylint: disable=redefined-outer-name         # pytest fixtures are injected by parameter name

from typing import get_args
from pathlib import Path

import pytest

from core.constants import Book
from scripts.corpus.corpus_models import (BookSchema, ChapterSchema, CorpusSchema, Labels,
                                          ProfileEvidence, Provenance, compute_corpus_id,
                                          record_path)
from scripts.corpus.sampling import ( iqr_outliers, select_book_sample, evidence_path,
                                     read_evidence, select_corpus_sample, write_evidence, main)

CORPUS_ID = "680db04cf48248ce"
# labels: {"first", "last", "shortest", "longest", "iqr_outlier", "random"}
ALL_LABELS = set(get_args(Labels))

# Ten typical chapters around 5,000 words, plus one short and one long outlier.
TYPICAL = dict(enumerate([4800, 4900, 5000, 5100, 5200, 4950, 5050, 4850, 5150, 5000], start=1))

# 12 chapters: ch 5 shortest (1500, outlier), ch 9 longest (9000, outlier); others ~5000.
COUNTS = [5000, 4800, 5100, 4900, 1500, 5200, 4950, 5050, 9000, 4850, 5150, 5000]

## Helpers & Fixtures

def make_book(word_counts: list[int], titles_in_text: bool = True,
              book: Book = Book.BOOK_3) -> BookSchema:
    """Book with chapters 1..N whose word counts are given in order."""
    chapters = {
        n: ChapterSchema(title=f"Ch {n}", title_in_text=titles_in_text, number=n,
                         filename=f"{book.value}chapter_{n:02d}.txt", character_count=words * 5,
                         word_count=words, sha256=f"{n:064x}")
        for n, words in enumerate(word_counts, start=1)
    }
    return BookSchema(name=book, expected_chapters=len(chapters), published_year=1999, isbn=None,
                      evidence=ProfileEvidence(source="test"), chapters=chapters)


def random_picks(sample: dict[int, list[Labels]]) -> list[int]:
    return [n for n, why in sample.items() if "random" in why]

@pytest.fixture
def record() -> CorpusSchema:
    """Two-book profiled record; book 7 inserted first to check the output is sorted anyway."""
    content = {Book.BOOK_7: make_book(COUNTS, titles_in_text=False, book=Book.BOOK_7),
               Book.BOOK_3: make_book(COUNTS, titles_in_text=True, book=Book.BOOK_3)}
    return CorpusSchema(
        schema_version="0.1", corpus_id=compute_corpus_id(content), status="profiled",
        provenance=Provenance(source_type="community", origin="test", acquired_from="test",
                              extraction_script="test"),
        corpus_root="data/06_books", scope="test", content=content)


def write_record(record: CorpusSchema, corpus_root: Path) -> None:
    """Put a record where main() looks for it (corpus_root/corpus_record.json)."""
    record_path(corpus_root).write_text(record.model_dump_json(), encoding="utf-8")


def select(corpus_root: Path) -> int:
    return main(["--corpus-root", str(corpus_root), "select"])

## iqr_outliers tests

def test_planted_outliers_both_tails_flagged():
    chapters = {**TYPICAL, 11: 1500, 12: 9000}
    assert iqr_outliers(chapters) == {11, 12}


def test_typical_book_has_no_outliers():
    assert iqr_outliers(TYPICAL) == set()


def test_all_chapters_same_length_returns_empty_set():
    # IQR = 0: no spread, so no basis for outliers (not "every different chapter")
    assert iqr_outliers({n: 5000 for n in range(1, 11)}) == set()


@pytest.mark.parametrize("chapters", [{}, {1: 100}, {1: 100, 2: 5000, 3: 9000}])
def test_fewer_than_four_chapters_returns_empty_set(chapters):
    assert iqr_outliers(chapters) == set()


def test_chapter_exactly_on_fence_is_not_flagged():
    # sorted 10, 20, 30, 40, 70 → Q1 = 20, Q3 = 40, IQR = 20, upper fence = 40 + 1.5*20 = 70
    on_fence = {1: 10, 2: 20, 3: 30, 4: 40, 5: 70}
    assert iqr_outliers(on_fence) == set()


def test_chapter_just_past_fence_is_flagged():
    # same quartiles (Q3 is still the 4th value), upper fence 70 → 71 is strictly above it
    past_fence = {1: 10, 2: 20, 3: 30, 4: 40, 5: 71}
    assert iqr_outliers(past_fence) == {5}


def test_larger_multiplier_flags_fewer_chapters():
    past_fence = {1: 10, 2: 20, 3: 30, 4: 40, 5: 71}
    assert iqr_outliers(past_fence, multiplier=3.0) == set()


def test_does_not_modify_input():
    chapters = {**TYPICAL, 11: 1500}
    before = dict(chapters)
    iqr_outliers(chapters)
    assert chapters == before

## select_book_sample tests

# --- rules ---------------------------------------------------------------------
def test_every_reason_is_a_valid_label():
    sample = select_book_sample(make_book(COUNTS, titles_in_text=False), CORPUS_ID)
    assert all(set(why) <= ALL_LABELS for why in sample.values())


def test_rule_chapters_selected_with_reasons():
    sample = select_book_sample(make_book(COUNTS), CORPUS_ID)
    assert "first" in sample[1] and "last" in sample[12]
    assert sample[5] == ["shortest", "iqr_outlier"]
    assert sample[9] == ["longest", "iqr_outlier"]


def test_chapter_with_several_reasons_gets_one_entry():
    # chapter 1 is both first and shortest
    sample = select_book_sample(make_book([1000, 5000, 5100, 4900, 5050, 4950]), CORPUS_ID)
    assert sample[1][:2] == ["first", "shortest"]
    assert list(sample).count(1) == 1


def test_output_sorted_by_chapter():
    sample = select_book_sample(make_book(COUNTS), CORPUS_ID)
    assert list(sample) == sorted(sample)


# --- random pick -----------------------------------------------------------------
def test_titled_book_gets_one_random_chapter():
    assert len(random_picks(select_book_sample(make_book(COUNTS), CORPUS_ID))) == 1


def test_untitled_book_gets_two_random_chapters():
    sample = select_book_sample(make_book(COUNTS, titles_in_text=False), CORPUS_ID)
    assert len(random_picks(sample)) == 2


def test_random_chapters_are_distinct_and_not_rule_selected():
    sample = select_book_sample(make_book(COUNTS, titles_in_text=False), CORPUS_ID)
    picks = random_picks(sample)
    assert len(set(picks)) == len(picks)
    assert all(sample[n] == ["random"] for n in picks)   # random never lands on a rule chapter


def test_random_pick_capped_at_pool_size():
    # 3 chapters: ch 1 first+shortest, ch 3 last+longest → pool is {2}; untitled wants 2, gets 1
    sample = select_book_sample(make_book([1000, 5000, 9000], titles_in_text=False), CORPUS_ID)
    assert random_picks(sample) == [2]


def test_empty_pool_gives_no_random_pick():
    # 2 chapters: both rule-selected → nothing left to draw from, and no error
    sample = select_book_sample(make_book([1000, 9000], titles_in_text=False), CORPUS_ID)
    assert random_picks(sample) == []


# --- determinism -----------------------------------------------------------------
def test_same_inputs_give_same_sample():
    book = make_book(COUNTS, titles_in_text=False)
    assert select_book_sample(book, CORPUS_ID) == select_book_sample(book, CORPUS_ID)


def test_different_corpus_id_can_change_random_pick():
    book = make_book(list(range(5000, 5040)), titles_in_text=False)   # 40 chapters, big pool
    picks = {tuple(random_picks(select_book_sample(book, f"corpus{i}"))) for i in range(5)}
    assert len(picks) > 1


def test_book_is_part_of_the_seed():
    # seeded per book (corpus_id:book.value): identical lengths in two books need not
    # give the same random pick, so one book's sample never depends on another's draw
    counts = list(range(5000, 5040))                                   # 40 chapters, big pool
    picks = {book: random_picks(select_book_sample(make_book(counts, False, book), CORPUS_ID))
             for book in (Book.BOOK_3, Book.BOOK_4, Book.BOOK_7)}
    assert len({tuple(p) for p in picks.values()}) > 1


## select_corpus_sample

def test_rows_cover_every_book(record):
    rows = select_corpus_sample(record)
    assert {r.book for r in rows} == {Book.BOOK_3, Book.BOOK_7}


def test_every_row_carries_the_corpus_id(record):
    assert all(r.corpus_id == record.corpus_id for r in select_corpus_sample(record))


def test_rows_sorted_by_book_then_chapter(record):
    keys = [(r.book.value, r.chapter) for r in select_corpus_sample(record)]
    assert keys == sorted(keys)


def test_one_row_per_sampled_chapter(record):
    keys = [(r.book, r.chapter) for r in select_corpus_sample(record)]
    assert len(keys) == len(set(keys))


def test_rows_start_unreviewed_in_round_one(record):
    assert all((r.round, r.result, r.notes) == (1, "", "") for r in select_corpus_sample(record))


def test_same_record_gives_same_rows(record):
    assert select_corpus_sample(record) == select_corpus_sample(record)


## evidence_path, write_evidence, read_evidence

def test_evidence_path_carries_corpus_id(tmp_path):
    path = evidence_path(tmp_path, "abc123")
    assert path == tmp_path / "fidelity_evidence" / "fidelity_evidence_abc123.csv"


def test_round_trip_preserves_rows(record, tmp_path):
    rows = select_corpus_sample(record)
    path = evidence_path(tmp_path, record.corpus_id)
    write_evidence(rows, path)
    assert read_evidence(path) == rows


def test_reviewer_edits_survive_round_trip(record, tmp_path):
    rows = select_corpus_sample(record)
    rows[0] = rows[0].model_copy(update={"result": "pass", "notes": "matches, with a comma"})
    path = evidence_path(tmp_path, record.corpus_id)
    write_evidence(rows, path)
    assert read_evidence(path)[0].notes == "matches, with a comma"


def test_write_creates_missing_folder(record, tmp_path):
    path = evidence_path(tmp_path / "new_root", record.corpus_id)
    write_evidence(select_corpus_sample(record), path)
    assert path.is_file()


def test_csv_holds_readable_values(record, tmp_path):
    path = evidence_path(tmp_path, record.corpus_id)
    write_evidence(select_corpus_sample(record), path)
    text = path.read_text()
    assert "prisoner_of_azkaban_" in text and "Book.BOOK_3" not in text
    assert "corpus_id,book,chapter,reason,round,result,notes" in text

## main / select
def test_select_writes_review_csv(record, tmp_path):
    write_record(record, tmp_path)
    assert select(tmp_path) == 0
    assert read_evidence(evidence_path(tmp_path, record.corpus_id)) == select_corpus_sample(record)


def test_select_does_not_overwrite_existing_csv(record, tmp_path, capsys):
    write_record(record, tmp_path)
    select(tmp_path)
    path = evidence_path(tmp_path, record.corpus_id)
    path.write_text(path.read_text() + "reviewer edits\n")       # stand-in for filled-in results
    before = path.read_text()

    assert select(tmp_path) == 0
    assert path.read_text() == before
    assert "already selected" in capsys.readouterr().out


def test_select_skips_corpus_that_is_not_profiled(record, tmp_path, capsys):
    write_record(record.model_copy(update={"status": "superseded"}), tmp_path)
    assert select(tmp_path) == 0
    assert not evidence_path(tmp_path, record.corpus_id).exists()
    assert "nothing to sample" in capsys.readouterr().out


def test_no_step_given_shows_usage():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0        # argparse: required subcommand missing
