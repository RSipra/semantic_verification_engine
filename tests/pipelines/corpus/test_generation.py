"""
Unit tests for scripts/pipelines/generate_questions/generate_questions.py.

Starts with get_chapters; the scratchpad branch tests (scratch_test_generation_branches.py)
move here later.
"""
# pylint: disable=missing-function-docstring   # test names describe the check

from core.constants import Book
from scripts.pipelines.generate_questions.generate_questions import get_chapters


# --- get_chapters ------------------------------------------------------------------------
def test_get_chapters_reads_the_given_folder(tmp_path):
    for n in (1, 2, 12):
        (tmp_path / f"prisoner_of_azkaban_chapter_{n:02d}.txt").write_text("x")
    paths = get_chapters.fn([Book.BOOK_3], target_book_folder=tmp_path, chapter_filter=[1, 12])
    assert [p.name for p in paths] == ["prisoner_of_azkaban_chapter_01.txt",
                                       "prisoner_of_azkaban_chapter_12.txt"]
