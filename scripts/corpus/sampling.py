"""
Project: SVE (ref implementation: Harry Potter Trivia)
Phase 2: Content Generation (Corpus validation before generation pipeline)

Sampling methods for validation of corpus

Selects the chapters for the fidelity check and writes the review CSV
(fidelity_evidence/fidelity_evidence_<corpus_id>.csv).
SampleReviewRow = one sampled chapter: why it was chosen (reason), which round,
and the reviewer's result + notes. Hand-edited, so it is validated when read back.
The review helper later summarises these rows into the record's FidelitySample
(see corpus_models: "Who writes what, and when").
"""
from pathlib import Path
from statistics import quantiles
import logging
import random
from collections import defaultdict

import pandas as pd

from scripts.corpus.corpus_models import CorpusSchema, BookSchema, SampleReviewRow, Labels

logger = logging.getLogger(__name__)

def iqr_outliers(chapters: dict[int, int], multiplier: float = 1.5) -> set[int]:
    """
    Return chapter numbers whose word counts are outliers by the IQR method.

    Outliers lie strictly below Q1 - multiplier*IQR or strictly above Q3 + multiplier*IQR
    (both tails: short → possible truncation, long → possible merged chapters).
    Quartiles use method='inclusive': the chapters are the whole book (a population,
    not a sample); this also matches numpy's default.

    Returns an empty set when there is no basis for outliers: fewer than 4 chapters,
    or IQR = 0 (all chapters the same length).
    """

    if len(chapters) < 4:
        logger.debug("fewer than 4 chapters: no basis for IQR outliers")
        return set()  # not enough data to compute IQR

    # calculate outlier fences (Q1 - k*IQR, Q3 + k*IQR)
    q1, _, q3 = quantiles(chapters.values(), n=4, method="inclusive")   # median unused
    iqr = q3 - q1

    if iqr == 0:
        logger.debug("IQR is zero, all chapters have the same length")
        return set()  # all chapters have the same length

    lower_fence = q1 - multiplier * iqr
    upper_fence = q3 + multiplier * iqr

    # filter chapters
    return {n for n, words in chapters.items() if words < lower_fence or words > upper_fence}


def select_book_sample(book_record: BookSchema,
                                corpus_id: str) -> dict[int, list[Labels]]:
    """
    Select chapters for fidelity review from one book: chapter number → reasons.

    Rules: first, last, shortest, longest, IQR outliers (both tails), plus a seeded random
    pick from the remaining chapters —> 1 if every chapter's title is in its text, else 2.
    Seeded per book (f"{corpus_id}_{book.name.value}") so the same corpus always gives the
    same sample, independent of other books.
    """

    wordcounts = {n: ch.word_count for n, ch in book_record.chapters.items()}
    labels: dict[int, list[Labels]] = defaultdict(list)

    labels[min(wordcounts)].append('first')
    labels[max(wordcounts)].append('last')
    labels[min(wordcounts, key=lambda n: wordcounts[n])].append('shortest')
    labels[max(wordcounts, key=lambda n: wordcounts[n])].append('longest')
    for n in iqr_outliers(wordcounts):
        labels[n].append('iqr_outlier')

    # list is sorted so that random selection with seed is deterministic
    remaining_chapters = sorted(set(wordcounts) - set(labels))
    n_random = 1 if all(ch.title_in_text for ch in book_record.chapters.values()) else 2
    rng= random.Random(f"{corpus_id}_{book_record.name.value}")
    for n in rng.sample(remaining_chapters, k=min(n_random, len(remaining_chapters))):
        labels[n].append('random')

    return dict(sorted(labels.items()))


def select_corpus_sample(record: CorpusSchema) -> list[SampleReviewRow]:
    """
    Sample chapters across all books of a profiled corpus: one SampleReviewRow per chapter.
       
    Calls select_book_sample per book; rows are sorted by book, then chapter, so the same
    corpus always yields the same file. result and notes start empty and are filled in by
    the reviewer (see ADR-P2-026 for what to record).
    """

    # for each book in corpus, select chapters for review and create a df for manual review
    rows = [
            SampleReviewRow(
                corpus_id=record.corpus_id,
                book=book_name,
                chapter=chapter,
                reason=labels)
            for book_name, book in record.content.items()
            for chapter, labels in select_book_sample(book, record.corpus_id).items()
        ]
    return sorted(rows, key=lambda r: (r.book.value, r.chapter))


def evidence_path(corpus_root: Path, corpus_id: str) -> Path:
    """Where the fidelity review CSV for this corpus lives."""
    return corpus_root / "fidelity_evidence" / f"fidelity_evidence_{corpus_id}.csv"


def write_evidence(rows: list[SampleReviewRow], path: Path) -> None:
    """
    Write review rows to CSV (reason as a JSON list via SampleReviewRow). Overwrites: callers
    decide whether writing is allowed (see main).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([r.model_dump(mode="json") for r in rows]).to_csv(path, index=False)


def read_evidence(path: Path) -> list[SampleReviewRow]:
    """
    Read the (hand-edited) review CSV back into validated rows. dtype=str and
    keep_default_na=False hand cells over exactly as written, so empty results stay ''.
    
    Returns List[SampleReviewRow]
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    return [SampleReviewRow.model_validate(r) for r in df.to_dict("records")]
