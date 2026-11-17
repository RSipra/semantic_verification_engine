"""
Project: SVE (ref implementation: Harry Potter Trivia)
Phase 2: Content Generation (Corpus validation before generation pipeline)

Sampling methods for validation of corpus
"""
from pathlib import Path
from statistics import quantiles
import logging
import random
from collections import defaultdict
from typing import Literal

from scripts.corpus.corpus_models import CorpusSchema, BookSchema

logger = logging.getLogger(__name__)

# standardize labels for chapter selection
Labels = Literal["first", "last", "shortest", "longest", "iqr_outlier", "random"]

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
        logger.debug("[DEBUG]: IQR is zero, all chapters have the same length")
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
    Seeded per book (f"{corpus_id}:{book.value}") so the same corpus always gives the same
    sample, independent of other books. exclude_from_random: chapters already covered
    (e.g. carried-forward evidence) so the random pick adds new ones.
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

def select_corpus_sample(corpus_record_path: str, output_path: str) -> None:
    """
   create evidence csv 
   1. read corpus schema from json
   2. for each book (def select_book_sample):
        - select chapters for review. first, last, shortest, longest U iqr outliers. 
        - select random n chapters .
            1<=n<3 for now. if book.chapter.title_in_text True for all chapters, n=1 else n =2.
            for random seed - use corpus id_book_number (same corpus, same sample)
        - create a df where each book.chapter is a row with fields for manual review.    
   3. write csv output (def write_evidence).
        - finalize df - add manual phase notes from a single dict matched to book, chapter.
        - check if file exists - if no write file. else logger - file already exists. check.
        - save file to memory - ddata/06_books/fidelity_evidence/fidelity_evidence_<corpus_id>.csv
   
   result and notes start empty and are filled in by the reviewer (see ADR-P2-026 for what to
   record)
    """
    json_data = Path(corpus_record_path).read_text(encoding="utf-8")
    corpus_record = CorpusSchema.model_validate_json(json_data)

    # for each book in corpus, select chapters for review and create a df for manual review
    for book, book_schema in corpus_record.content.items():
        
        # dict of chapters with reasons for selection: chapter number → list of reasons
        selected_chapters = select_book_sample(book_schema, corpus_record.corpus_id)
