"""
Shared test setup for tests/corpus.

pytest loads this file automatically: fixtures defined here (record) are available to every
test module in this folder by parameter name. Plain helpers (make_book, COUNTS) are imported
explicitly: from tests.corpus.conftest import make_book, COUNTS
"""
import pytest

from core.constants import Book
from scripts.corpus.corpus_models import (BookSchema, ChapterSchema, CorpusSchema,
                                          ProfileEvidence, Provenance, compute_corpus_id)

# 12 chapters: ch 5 shortest (1500, outlier), ch 9 longest (9000, outlier); others ~5000.
COUNTS = [5000, 4800, 5100, 4900, 1500, 5200, 4950, 5050, 9000, 4850, 5150, 5000]


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
