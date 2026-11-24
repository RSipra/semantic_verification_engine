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

from datetime import date
from typing import get_args
from pathlib import Path

import pytest

from core.constants import Book
from scripts.corpus.corpus_models import (CorpusSchema, Labels, FidelityReferences,
                                          SampleReviewRow, read_corpus_record, file_sha256,
                                          compute_corpus_id, record_path, changed_evidence,)
from scripts.corpus.sampling import (CHECK_SCOPE, iqr_outliers, select_book_sample, evidence_path,
                                     read_evidence, select_corpus_sample, write_evidence, main,
                                     passages, check_changed_chapters, references_path, run_promote,
                                     summarize_book)
from tests.corpus.conftest import COUNTS, make_book

CORPUS_ID = "680db04cf48248ce"
# labels: {"first", "last", "shortest", "longest", "iqr_outlier", "random"}
ALL_LABELS = set(get_args(Labels))

# Ten typical chapters around 5,000 words, plus one short and one long outlier.
TYPICAL = dict(enumerate([4800, 4900, 5000, 5100, 5200, 4950, 5050, 4850, 5150, 5000], start=1))


## Helpers & Fixtures

def random_picks(sample: dict[int, list[Labels]]) -> list[int]:
    return [n for n, why in sample.items() if "random" in why]


def save_record(record: CorpusSchema, corpus_root: Path) -> None:
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
    save_record(record, tmp_path)
    assert select(tmp_path) == 0
    assert read_evidence(evidence_path(tmp_path, record.corpus_id)) == select_corpus_sample(record)


def test_select_does_not_overwrite_existing_csv(record, tmp_path, capsys):
    save_record(record, tmp_path)
    select(tmp_path)
    path = evidence_path(tmp_path, record.corpus_id)
    path.write_text(path.read_text() + "reviewer edits\n")       # stand-in for filled-in results
    before = path.read_text()

    assert select(tmp_path) == 0
    assert path.read_text() == before
    assert "already selected" in capsys.readouterr().out


def test_select_skips_corpus_that_is_not_profiled(record, tmp_path, capsys):
    save_record(record.model_copy(update={"status": "superseded"}), tmp_path)
    assert select(tmp_path) == 0
    assert not evidence_path(tmp_path, record.corpus_id).exists()
    assert "nothing to sample" in capsys.readouterr().out


def test_no_step_given_shows_usage():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code != 0        # argparse: required subcommand missing


# --- passages ----------------------------------------------------------------------------
def test_passages_cut_start_middle_end():
    text = "".join(f"{i:04d}" for i in range(250))          # 1,000 chars, position-coded
    parts = passages(text, length=300)
    assert parts["START"] == text[:300]
    assert parts["END"] == text[-300:]
    assert parts["MIDDLE"] == text[350:650]                 # centred on the halfway point (500)


def test_passages_collapse_whitespace():
    parts = passages("line one\n\n  line   two\nline three", length=300)
    assert parts["START"] == "line one line two line three"


def test_short_text_returned_whole_without_error():
    parts = passages("Just a short chapter.", length=300)
    assert set(parts.values()) == {"Just a short chapter."}


# --- show (via main) ---------------------------------------------------------------------
def write_chapter_files(record: CorpusSchema, corpus_root: Path) -> None:
    """A recognisable text file for every chapter in the record, named as the record says."""
    for book in record.content.values():
        for n, chapter in book.chapters.items():
            body = f"START-{book.name.value}{n} " + "filler " * 200 + f" END-{book.name.value}{n}"
            (corpus_root / chapter.filename).write_text(body, encoding="utf-8")


def show(corpus_root: Path, *books: str) -> int:
    args = ["--corpus-root", str(corpus_root), "show"]
    return main(args + (["--books", *books] if books else []))


@pytest.fixture
def selected(record, tmp_path):
    """Corpus root with record, chapter files and a selected sample (show's preconditions)."""
    save_record(record, tmp_path)
    write_chapter_files(record, tmp_path)
    select(tmp_path)
    return tmp_path


def test_show_prints_one_block_per_sampled_chapter(record, selected, capsys):
    assert show(selected) == 0
    out = capsys.readouterr().out
    assert out.count("=== ") == len(select_corpus_sample(record))
    assert out.count("[START]") == out.count("[MIDDLE]") == out.count("[END]") == out.count("=== ")


def test_show_header_names_book_chapter_title_and_reasons(record, selected, capsys):
    show(selected)
    out = capsys.readouterr().out
    first = select_corpus_sample(record)[0]
    title = record.content[first.book].chapters[first.chapter].title
    assert f"=== {first.book.value} ch {first.chapter} · '{title}'" in out
    assert ", ".join(first.reason) in out


def test_show_passages_come_from_the_right_file(record, selected, capsys):
    show(selected)
    out = capsys.readouterr().out
    first = select_corpus_sample(record)[0]
    assert f"START-{first.book.value}{first.chapter}" in out


def test_show_books_filter(selected, capsys):
    assert show(selected, "BOOK_3") == 0
    out = capsys.readouterr().out
    assert "prisoner_of_azkaban_" in out and "deathly_hallows_" not in out


def test_show_book_without_sampled_chapters(selected, capsys):
    assert show(selected, "BOOK_4") == 0            # not in the fixture corpus: nothing sampled
    assert "no sampled chapters" in capsys.readouterr().out


def test_show_before_select_returns_error(record, tmp_path, capsys):
    save_record(record, tmp_path)                     # record exists, no review CSV yet
    assert show(tmp_path) == 1
    assert "run `select` first" in capsys.readouterr().out


def test_show_rejects_comma_separated_books(selected):
    with pytest.raises(SystemExit):
        show(selected, "BOOK_3,")                     # argparse choices: spaces, not commas


# --- summarize_book ----------------------------------------------------------------------
TODAY = date(2026, 11, 23)


def review_row(chapter: int, reason: list[Labels], round_: int = 1) -> SampleReviewRow:
    return SampleReviewRow(corpus_id=CORPUS_ID, book=Book.BOOK_3, chapter=chapter,
                           reason=reason, round=round_, result="pass")


def test_summary_lists_chapters_sorted():
    rows = [review_row(12, ["last"]), review_row(1, ["first"]), review_row(5, ["shortest"])]
    assert summarize_book(rows, "ref", TODAY).chapters == [1, 5, 12]


def test_summary_counts_every_label_once_per_chapter():
    # ch 5 carries two labels: each is counted
    rows = [review_row(1, ["first"]), review_row(5, ["shortest", "iqr_outlier"]),
            review_row(7, ["random"]), review_row(9, ["random"])]
    strategy = summarize_book(rows, "ref", TODAY).sampling_strategy
    assert strategy == "round 1: first ×1, iqr_outlier ×1, random ×2, shortest ×1"


def test_summary_names_every_round_present():
    rows = [review_row(1, ["first"]), review_row(4, ["random"], round_=2)]
    assert summarize_book(rows, "ref", TODAY).sampling_strategy.startswith("round 1, 2:") # pylint: disable=no-member
    # pydantic field, FieldInfo false positive

def test_summary_passes_through_reference_date_and_scope():
    sample = summarize_book([review_row(1, ["first"])], "UK e-book, ISBN x", TODAY)
    assert (sample.reference, sample.date_checked, sample.check_scope, sample.result) == \
        ("UK e-book, ISBN x", TODAY, CHECK_SCOPE, "pass")


# --- promote: fixtures and helpers ---------------------------------------------------------
def save_profiled_corpus(record: CorpusSchema, corpus_root: Path) -> CorpusSchema:
    """
    Write chapter files, then record their real sha256 (and the matching corpus_id), as
    profiling would. make_book's placeholder hashes would otherwise fail promote's check.
    """
    write_chapter_files(record, corpus_root)
    content = {}
    for book, book_record in record.content.items():
        chapters = {n: ch.model_copy(update={"sha256": file_sha256(corpus_root / ch.filename)})
                    for n, ch in book_record.chapters.items()}
        content[book] = book_record.model_copy(update={"chapters": chapters})
    data = record.model_dump()
    data.update(content={b: bk.model_dump() for b, bk in content.items()},
                corpus_id=compute_corpus_id(content))
    profiled = CorpusSchema.model_validate(data)
    save_record(profiled, corpus_root)
    return profiled


def set_results(corpus_root: Path, corpus_id: str, result: str = "pass") -> None:
    """Fill every row's result, as the reviewer would."""
    path = evidence_path(corpus_root, corpus_id)
    write_evidence([r.model_copy(update={"result": result}) for r in read_evidence(path)], path)


def write_references(corpus_root: Path, corpus_id: str, books,
                     claimed_id: str | None = None) -> None:
    """References file for corpus_id; claimed_id puts a different corpus_id inside the file."""
    refs = FidelityReferences(corpus_id=claimed_id or corpus_id,
                              references={b: f"reference edition for {b.value}" for b in books})
    references_path(corpus_root, corpus_id).write_text(refs.model_dump_json(), encoding="utf-8")


def promote(corpus_root: Path) -> int:
    return main(["--corpus-root", str(corpus_root), "promote"])


@pytest.fixture
def reviewed(record, tmp_path):
    """Corpus root ready to certify: matching hashes, sample selected, all pass, references."""
    profiled = save_profiled_corpus(record, tmp_path)
    select(tmp_path)
    set_results(tmp_path, profiled.corpus_id)
    write_references(tmp_path, profiled.corpus_id, profiled.content)
    return tmp_path, profiled


# --- check_changed_chapters -----------------------------------------------------------------
def test_unchanged_chapters_report_nothing(reviewed):
    root, rec = reviewed
    assert check_changed_chapters(root, rec) == []


def test_edited_chapter_is_reported(reviewed):
    root, rec = reviewed
    chapter = rec.content[Book.BOOK_3].chapters[2]
    (root / chapter.filename).write_text("edited", encoding="utf-8")
    assert check_changed_chapters(root, rec) == [
        f"prisoner_of_azkaban_ ch 2: changed since profiling ({chapter.filename})"]


def test_missing_chapter_is_reported(reviewed):
    root, rec = reviewed
    chapter = rec.content[Book.BOOK_7].chapters[3]
    (root / chapter.filename).unlink()
    assert check_changed_chapters(root, rec) == [
        f"deathly_hallows_ ch 3: file missing ({chapter.filename})"]


# --- promote: happy path ----------------------------------------------------------------------
def test_promote_certifies_reviewed_corpus(reviewed):
    root, _ = reviewed
    assert run_promote(root, today=TODAY) == 0
    certified = read_corpus_record(root)
    assert certified.status == "certified"
    assert (certified.certification_method, certified.date_certified) == ("manual_review", TODAY)


def test_promote_writes_one_passing_sample_per_book(reviewed):
    root, rec = reviewed
    run_promote(root, today=TODAY)
    certified = read_corpus_record(root)
    rows = select_corpus_sample(rec)
    for book, book_record in certified.content.items():
        sample = book_record.fidelity_sample
        assert sample is not None and sample.result == "pass" and sample.date_checked == TODAY
        assert sample.chapters == [r.chapter for r in rows if r.book == book]
        assert sample.reference == f"reference edition for {book.value}"


def test_promote_binds_both_evidence_files_by_hash(reviewed):
    root, rec = reviewed
    run_promote(root, today=TODAY)
    certified = read_corpus_record(root)
    assert set(certified.evidence_files) == {
        evidence_path(root, rec.corpus_id).relative_to(root).as_posix(),
        references_path(root, rec.corpus_id).relative_to(root).as_posix()}
    assert changed_evidence(root, certified.evidence_files) == []


def test_promote_leaves_profile_fields_untouched(reviewed):
    root, rec = reviewed
    run_promote(root, today=TODAY)
    certified = read_corpus_record(root)
    assert certified.provenance == rec.provenance
    for book, book_record in certified.content.items():
        assert book_record.chapters == rec.content[book].chapters
        assert book_record.evidence == rec.content[book].evidence


def test_promote_runs_from_the_cli(reviewed, capsys):
    root, rec = reviewed
    assert promote(root) == 0
    assert f"certified corpus {rec.corpus_id}" in capsys.readouterr().out


# --- promote: status -------------------------------------------------------------------------
def test_promote_on_certified_corpus_does_nothing(reviewed, capsys):
    root, _ = reviewed
    run_promote(root, today=TODAY)
    before = record_path(root).read_bytes()
    assert promote(root) == 0
    assert record_path(root).read_bytes() == before
    assert "already certified" in capsys.readouterr().out


def test_promote_refuses_superseded_record(reviewed, capsys):
    root, rec = reviewed
    save_record(rec.model_copy(update={"status": "superseded"}), root)
    assert promote(root) == 1
    assert "superseded" in capsys.readouterr().out


def test_promote_refuses_without_record(tmp_path, capsys):
    assert promote(tmp_path) == 1
    assert "corpus record not found" in capsys.readouterr().out


# --- promote: refusals (each spoils one input; nothing is written) -----------------------------
def drop_first_row(root: Path, rec: CorpusSchema) -> None:
    path = evidence_path(root, rec.corpus_id)
    write_evidence(read_evidence(path)[1:], path)


def add_unplanned_row(root: Path, rec: CorpusSchema) -> None:
    path = evidence_path(root, rec.corpus_id)
    rows = read_evidence(path)
    planned = {r.chapter for r in rows if r.book == Book.BOOK_3}
    spare = min(set(rec.content[Book.BOOK_3].chapters) - planned)
    extra = rows[0].model_copy(update={"book": Book.BOOK_3, "chapter": spare})
    write_evidence(rows + [extra], path)


def set_one_result(result: str):
    def spoil(root: Path, rec: CorpusSchema) -> None:
        path = evidence_path(root, rec.corpus_id)
        rows = read_evidence(path)
        rows[0] = rows[0].model_copy(update={"result": result})
        write_evidence(rows, path)
    return spoil


def break_csv_cell(root: Path, rec: CorpusSchema) -> None:
    path = evidence_path(root, rec.corpus_id)
    path.write_text(path.read_text(encoding="utf-8").replace(",pass,", ",maybe,", 1),
                    encoding="utf-8")


REFUSALS = {
    "csv missing": (lambda root, rec: evidence_path(root, rec.corpus_id).unlink(),
                    "review CSV not found"),
    "references missing": (lambda root, rec: references_path(root, rec.corpus_id).unlink(),
                           "references file not found"),
    "csv invalid": (break_csv_cell, "review CSV invalid"),
    "references for another corpus": (
        lambda root, rec: write_references(root, rec.corpus_id, rec.content,
                                           claimed_id="other_corpus"),
        "references file carries corpus_id"),
    "chapter edited": (
        lambda root, rec: (root / rec.content[Book.BOOK_3].chapters[1].filename)
        .write_text("edited", encoding="utf-8"),
        "changed since profiling"),
    "row deleted": (drop_first_row, "planned chapters not in the review CSV"),
    "row added": (add_unplanned_row, "not in the planned sample"),
    "reference missing for a book": (
        lambda root, rec: write_references(root, rec.corpus_id, [Book.BOOK_3]),
        "no reference for: deathly_hallows_"),
    "result blank": (set_one_result(""), "not reviewed"),
    "result fail": (set_one_result("fail"), "escalate per ADR-P2-026"),
}


@pytest.mark.parametrize("spoil, message", REFUSALS.values(), ids=REFUSALS.keys())
def test_promote_refuses_and_writes_nothing(reviewed, capsys, spoil, message):
    root, rec = reviewed
    spoil(root, rec)
    before = record_path(root).read_bytes()

    assert promote(root) == 1
    assert record_path(root).read_bytes() == before
    out = capsys.readouterr().out
    assert "promote refused" in out and message in out


def test_promote_reports_both_missing_inputs_together(reviewed, capsys):
    root, rec = reviewed
    evidence_path(root, rec.corpus_id).unlink()
    references_path(root, rec.corpus_id).unlink()
    assert promote(root) == 1
    out = capsys.readouterr().out
    assert "review CSV not found" in out and "references file not found" in out
