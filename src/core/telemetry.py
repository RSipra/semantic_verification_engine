"""
Telemetry - models and helpers

Currently models for LLM call records. Other accounting (evaluator tier routing,
local inference timing) would live here too if it needs the same treatment.

One accounting line per API call: identity, model, cost, and what the call
produced. The base carries what is true of every call; each pipeline's subclass
adds only its own fields, so a record documents its own shape.

Shared by the offline generation and enrichment passes. The validation pipeline
and the runtime judge will extend the same base once their LLM calls are
consolidated into a common service.

"""
from pydantic import BaseModel, model_validator, ConfigDict
from core.constants import QuestionType

## LLM API CALLS

# common to all llm calls
class CallEntry(BaseModel):
    """
    One accounting line for a single LLM API call.

    Written to the run's calls jsonl as each call completes, and read back by
    save_run_completion to derive the run totals. Records that cost tokens but
    produced nothing are still entries — a call that failed is accounted for,
    not omitted.

    Dump with model_dump(mode="json") so the enum serialisesto its value. All
    fields are written, including optional ones set to None — a missing key then
    means the entry's shape lacks that field, not that it was unset.    
    """
    # validator re-runs if a value is reassigned; unknown fields raise
    model_config = ConfigDict(validate_assignment=True, extra='forbid')

    call_id: str
    question_type: QuestionType
    model: str
    prompt_version: str
    tokens: dict
    # location where output jsonl saved (only for valid, empty for quarantined call)
    output_file: str | None = None
    # the number of llm records saved in jsonl checkpoint files
    records_written: int = 0  
    # if llm call fails, add failure mode to call entry
    failure_mode: str | None = None

    # make sure the output file name is recorded for valid records
    @model_validator(mode ='after')
    def output_file_matches_records(self):
        """Records that were written must name the file they went to"""
        if self.records_written > 0 and not self.output_file:
            raise ValueError("records were written but no output_file was recorded")
        return self

    @model_validator(mode="after")
    def failed_calls_produced_nothing(self):
        """A call that failed before evaluation cannot have written records"""
        if self.failure_mode and self.records_written:
            raise ValueError("a failed call cannot have written records")
        return self

## Question generation pipeline (Prefect)

# question generation llm pass
class GenerationCallEntry(CallEntry):
    """
    A generation call: one batch (default 2 full chapters at a time) for one question 
    type in a single api call.

    Source files are whole chapters by default, or thematic excerpts for a
    thematic run. source_files is how many went into this call.

    No records_sent: the model decides how many questions a batch yields, so
    there is no expected count to compare against.    
    """
    batch_id: str
    # from the batch plan, not len(source_files) — a thematic
    # run can cover fewer chapters than it has excerpt file
    chapter_count: int
    source_files: list[str]
            
class EnrichmentCallEntry(CallEntry):
    """
    One API call in an enrichment pass.

    Adding how many records went into the call,
    and which slice of the pass's partition they came from.

    - `records_sent` is the denominator for this call's loss accounting —
       records_sent = records_written + records_rejected + batch_loss, each measured
       at a different point (send / DTO construction / disk write).
    - `chunk_index` is the position of this call's input within its question type's
       grouping, and is the join key back to the manifest. Generation has no
       equivalent: its input is a set of source documents, not an ordered partition,
       so it records which files it covered instead.
    - `quarantined` — <what it holds>
    """
    records_sent: int
    # position of this call's input slice within its pass's partition 
    # (e.g. MCQ questions split into N question batches for enrichment)
    chunk_index: int  
    quarantined: dict | None = None
