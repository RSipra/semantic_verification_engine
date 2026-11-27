"""
_summary_
"""
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from scripts.corpus.sampling import load_input
from scripts.corpus.corpus_models import (ChapterSchema, CorpusSchema, bytes_sha256,
                                          changed_evidence, read_corpus_record, record_path)

class PreflightResult(BaseModel):
    """ What a passing run takes from the certified record (manifest now, lineage later)."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    corpus_id: str
    chapter_sha256: dict[str, str]    # chapter.filename: chapter.sha


def check_evidence(record: CorpusSchema, corpus_root: Path) -> list[str]:
    """Problems for evidence files missing or edited since certification (empty = intact)."""
    return [f"evidence file missing or edited since certification: {rel} "
            "(restore it, or re-certify with promote --recertify)"
            for rel in changed_evidence(corpus_root, record.evidence_files)]


def describe_change(raw: bytes, chapter: ChapterSchema) -> str:
    """How a chapter file differs from its certified record (diagnosis only; the hash decides)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "no longer valid UTF-8"
    chars, words = len(text), len(text.split())
    if chars == 0:
        how = "emptied"
    elif chars < chapter.character_count:
        how = "shorter: truncated or text removed"
    elif chars > chapter.character_count:
        how = "longer: text added"
    else:
        how = "same length: edited in place"
    return (f"characters {chapter.character_count:,} -> {chars:,}, "
            f"words {chapter.word_count:,} -> {words:,} ({how})")


def run_preflight(target_book_folder:Path, chapter_file_paths: list[Path])-> PreflightResult:
    """ 
    Inputs: target_folder, chapter_file_paths
1. load record (via load_input) — fails → stop
2. status == certified — not → stop
3. evidence changed → record the stop reason, raise, and don’t check the chapters.
4. nothing to check? (empty paths) → stop
5. build filename → record-chapter lookup (once)
6. for each path:
     no record chapter for path.name → problem
     hash != recorded sha256      → problem (+ how it changed)
7. any problems → record the stop reason, raise (all problems in the message)
8. pass → return <what the run needs from the record>
    """

    # 1. load record and chapter files:
    problems: list[str] = []   
    record = load_input("corpus record",
                        target_book_folder,
                        read_corpus_record,
                        problems,
                        hint=" (run qualify_corpus first)",
                        display_path=record_path(target_book_folder))

    if record is None:
        raise ValueError("Preflight refused the run: " + "; ".join(problems))

    # 2. check status:
    if record.status != "certified":
        raise ValueError("Preflight refused the run: "
                         f"corpus {record.corpus_id} is {record.status!r}, not 'certified'.")

    # 3. Has the evidence changed?
    problems += check_evidence(record, target_book_folder)
    if problems:
        raise ValueError("Preflight refused the run: " + "; ".join(problems))

    # 4. are the file paths provided
    if not chapter_file_paths:
        raise ValueError("Preflight refused the run: chapter files not provided.")

    # 5. lookup built once from the record: chapter file name -> certified chapter record
    certified = {chapter.filename: chapter
                 for book in record.content.values()
                 for chapter in book.chapters.values()}

    # 6. each file this run will read: in the record? same bytes? (collect, don't stop)
    chapter_sha256: dict[str, str] = {}
    for path in chapter_file_paths:
        chapter = certified.get(path.name)
        if chapter is None:
            problems.append(f"{path.name}: not in the certified corpus record")
            continue
        if not path.is_file():
            problems.append(f"{path.name}: file missing")
            continue
        raw = path.read_bytes()
        if bytes_sha256(raw) != chapter.sha256:
            problems.append(f"{path.name}: changed since certification "
                            f"({describe_change(raw, chapter)})")
            continue
        chapter_sha256[path.name] = chapter.sha256

    # 7. any problem -> refuse the run, listing every problem
    if problems:
        raise ValueError(f"Preflight refused the run: {len(problems)} problem(s): "
                         + "; ".join(problems))

    # 8. pass -> what the run needs from the record (manifest now, lineage later)
    return PreflightResult(corpus_id=record.corpus_id, 
                           chapter_sha256=chapter_sha256)
