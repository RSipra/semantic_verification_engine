"""
Project: SVE (ref implementation: Harry Potter Trivia)
Phase 2: Content Generation (Corpus validation before generation pipeline)

Sampling methods for validation of corpus
"""
from statistics import quantiles
import logging

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
        logger.debug("[DEBUG]: IQR is zero, all chapters have the same length")
        return set()  # all chapters have the same length

    lower_fence = q1 - multiplier * iqr
    upper_fence = q3 + multiplier * iqr

    # filter chapters
    return {n for n, words in chapters.items() if words < lower_fence or words > upper_fence}
