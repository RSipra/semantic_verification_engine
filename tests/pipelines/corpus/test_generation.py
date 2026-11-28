"""
Unit tests for scripts/pipelines/generate_questions/generate_questions.py.

Starts with get_chapters; the scratchpad branch tests (scratch_test_generation_branches.py)
move here later.
"""
# pylint: disable=missing-function-docstring   # test names describe the check
import json 
import logging
from core.constants import Book
from scripts.pipelines.generate_questions.generate_questions import get_chapters, process_and_save_response


# --- get_chapters ------------------------------------------------------------------------
def test_get_chapters_reads_the_given_folder(tmp_path):
    for n in (1, 2, 12):
        (tmp_path / f"prisoner_of_azkaban_chapter_{n:02d}.txt").write_text("x")
    paths = get_chapters.fn([Book.BOOK_3], target_book_folder=tmp_path, chapter_filter=[1, 12])
    assert [p.name for p in paths] == ["prisoner_of_azkaban_chapter_01.txt",
                                       "prisoner_of_azkaban_chapter_12.txt"]

# --- process_and_save_responses ---------------------------------------------------------     
# Lineage stamping in process_and_save_response (ADR-P2-027).

"""Lineage stamping in process_and_save_response (ADR-P2-027)."""
import json
import logging

from scripts.pipelines.generate_questions.generate_questions import process_and_save_response  # match the existing import style

SHA = "a" * 64
CORPUS_ID = "0123456789abcdef"
FILE = "book_chapter_01.txt"


def make_metadata(chapter_sha256: dict) -> dict:
    """Batch metadata with only the keys process_and_save_response reads."""
    return {
        "corpus_id": CORPUS_ID,
        "source_chapter_sha256": chapter_sha256,
        "model_name": "test-model",
        "timestamp": "2026-11-27T12:00:00+00:00",
        "prompt_id": "fr_master_prompt_test.txt",
        "generation_strategy_version": "generation_strategy_test",
        "question_type": "FR",
        "identifiers": {"pipeline_name": "pipe_q_gen_test"},
    }


def make_question() -> dict:
    """One parsed LLM question, invented text (no corpus text in tests)."""
    return {
        "question_type": "FR",
        "question": "What colour is the invented test door?",
        "answer": "Blue",
        "mcq_options": None,
        "llm_predicted_category": "Character Detail",
        "llm_predicted_difficulty": "Medium",
        "source_reference": "Book Chapter 01",
        "source_quote": "The invented test door was painted blue.",
    }


def run_process(tmp_path, chapter_sha256: dict):
    """Call process_and_save_response with one invented question; return its outputs and the file"""
    out = tmp_path / "q.jsonl"
    drafts, quarantine, generated = process_and_save_response(
        run_id="run",
        batch_id="batch",
        call_id="call",
        llm_pass="generation",
        parsed_response=[make_question()],
        output_file=out,
        full_metadata=make_metadata(chapter_sha256),
        finish_reason="STOP",
        logger=logging.getLogger("test")
    )
    return drafts, quarantine, generated, out


def test_lineage_stamped_on_dto_and_file(tmp_path):
    drafts, quarantine, generated, out = run_process(tmp_path, {FILE: SHA})

    assert generated == 1
    assert quarantine == []
    assert len(drafts) == 1
    assert drafts[0].corpus_id == CORPUS_ID
    assert drafts[0].source_chapter_sha256 == {FILE: SHA}

    record = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert record["corpus_id"] == CORPUS_ID
    assert record["source_chapter_sha256"] == {FILE: SHA}


def test_malformed_sha_quarantined(tmp_path):
    drafts, quarantine, generated, out = run_process(tmp_path, {FILE: "abc"})

    assert generated == 1                        # parsed, then rejected at DTO construction
    assert drafts == []
    assert len(quarantine) == 1
    assert not out.exists() or out.read_text(encoding="utf-8") == ""   # nothing written