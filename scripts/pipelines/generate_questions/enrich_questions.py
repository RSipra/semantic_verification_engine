"""
Project: SVE (ref implementation: Harry Potter Trivia)
Automated Prefect pipeline: enrichment of generated questions.
======================================================================
Two LLM enrichment passes (downstream of generation pass to produce core fields): 
   (1) lexical enrichment, (2) semantic enrichment.

Model chain (nothing mutates; each pass constructs the next class):
  DraftQuestion -> LexDraftQuestion.from_draft() -> SyntheticStandard.from_lex()
  Successful construction IS the validation gate.
  SyntheticStandard is SOT; mcq_options is Optional + type-conditional validator.

Prompt/model sync:
- Each prompt module declares one dict: {field: description + format hint}.
- Import-time assert: dict keys == model field-set diff for that pass.
- Template field block rendered from the same dict (single declaration, no drift).

Batching:
- Filter DraftQuestion list by question type (prompt coherence), chunk at
  CHUNK_SIZE (~15-20, config).
- Batch key = (book, chapter, type, chunk). Also the idempotency/resume key.
- syn_id echoed in prompt, required in response. Reconcile by set difference,
  never positionally.

Per pass:
- Build prompt (relevant cols only) -> LLM service call (src.engine.llm_service)
- Attach pass metadata (prompt version, model, timestamp)
- Write response jsonl -- CHECKPOINT, re-loadable into DTOs, not just a log
- Construct next DTO class

Failure handling:
- Transport error: retry w/ backoff (Prefect), then fail batch.
- Missing syn_ids: retry missing subset once, then quarantine.
- Unparseable record: quarantine (raw + reason).
- DTO Construction failure (critical null): quarantine.
- Warn thresholds: if >10% of a batch, >5% of run quarantined (monitored, 
  not enforced, see Structural failure thresholds below).

Exit: SyntheticStandard set -> staging pool (GCS) or direct handoff to
validation pipeline. Semantic checks (grounding, dedup, RAG-triad) stay in
the validation pipeline; this module owns structural contract only.

Structural failure thresholds
-----------------------------
Scope: structural contract only — did the LLM return something that
satisfies the DTO? (parseable response, ids reconciled, required fields
present and non-empty). Semantic quality (grounding, hallucination,
dedup) belongs to the validation pipeline.

Both are ratios of quarantined records to records the LLM returned:
  - max_batch_failure_rate: len(batch_quarantined) / len(parsed_responses)
      per API call (n≈20, noisy — 1 failure = 5%)
  - max_run_failure_rate: total_quarantined / total_processed
      accumulated across batches (less noisy)
  Values live in ENRICHMENT_STRATEGY, per pass.
  NB the denominator is records RETURNED, not records sent — a batch that
  fails before convert_to_dto (unparseable response, transport error)
  contributes nothing to either ratio and needs its own count.

Declared and monitored, NOT enforced. Breaches log a warning; the run
continues.

Why not enforced:
  - Bronze schema gate is the enforcer; nothing bad reaches Silver either way
  - failures are detected after the batch's tokens are already spent, so
    aborting only saves batches not yet started
  - no resume-from-checkpoint, so an abort costs a full re-run
  - tracer (n=50) showed zero structural failures — normal is not yet
    characterised, so the values are placeholders, not calibrated limits

Revisit enforcement when any of: a real run shows structural failures;
runs become unattended (no one watching logs to Ctrl-C); resume-from-
checkpoint exists.

>> Uses helpers from generate for now; refactor to common module after smoke test.

NOTE Timestamps: enrichment passes deliberately carry no timestamp of their own.
The record's `timestamp` is set at ingestion — generation for synthetic,
preprocessing for legacy — so both paths satisfy the model without a
source-conditional validator. Revisit only if enrichment becomes decoupled
from ingestion (e.g. backfilling a new field across existing records).
"""
## Setup
import json
import time
from datetime import datetime
import sys
import logging
from collections.abc import Sequence
from collections import defaultdict, Counter
from pathlib import Path
from pydantic import ValidationError
from prefect import flow, get_run_logger

from core.models import DraftQuestion
from scripts.pipelines.generate_questions.prompts.pipeline_config import ENRICHMENT_STRATEGY
from scripts.pipelines.generate_questions.generate_questions import (short_uuid,
                                                                     configure_api,
                                                                     make_api_call,
                                                                     append_jsonl,
                                                                     measure_template_tokens,
                                                                     calculate_token_metrics,
                                                                     save_run_completion,
                                                                     create_run_report,
                                                                     build_run_artifact_path,
                                                                     CONFIG_PATH, CALLS, QUARANTINE)

import notebook_support.notebook_config as nb_cfg

## 1. CONSTANTS, DTOs & CONFIGS
OUTPUT_DIR = nb_cfg.GENERATED_QUESTIONS_DIR
CORE_PROMPT_FIELDS = {'syn_id','question_type','question','answer','mcq_options'}

CHUNK_SIZE = 20     # number of questions per API call
lex_config = ENRICHMENT_STRATEGY["lex_enrichment"]
semantic_config = ENRICHMENT_STRATEGY["semantic_enrichment"]

test_path = OUTPUT_DIR / "fr_questions_prisoner_of_azkaban_chapter_01_run20260724_9882e5b1.jsonl"
RUNS_DIR = nb_cfg.RUNS_DIR
# standardized unique identifier for this question_generation script with version
PIPELINE_ID = "pipe_q_enrich_v00" 

## 2. TASKS & HELPERS

# read jsonl from file into DTO
def retrive_dto_from_jsonl_file(file_path: Path):
    """"""
    with open(file_path, "r", encoding="utf-8") as f:
        return [DraftQuestion.model_validate_json(line) for line in f if line.strip()]

def write_jsonl_checkpoint(draft_questions: list[DraftQuestion], output_file: Path):
    """
    Write a list of DTOs to a jsonl file for checkpointing.
    
    Writes a whole batch of DTOs, replacing the file. Uses model_dump_json
    so Pydantic types serialise correctly. For accumulating plain dicts,
    see `append_jsonl()`.
    
    Args:
        dtos: List of DTO objects to write to the file.
        output_file: Path to the output jsonl file.
    """
    with open(output_file, "w", encoding="utf-8") as f:
        for dto in draft_questions:
            f.write(dto.model_dump_json() + "\n")

# convert list of DTO into json dump for the prompt
def serialize_dtos_to_json(dto_list: list[DraftQuestion], prompt_fields: set[str])-> str:
    """
    Convert list of DTOs into a json ready for prompt injection.
    Args:
        dto_list (list[DTO]): List of DTO objects to serialize for prompt injection
        prompt_fields: Set of fields to include in the prompt payload.
    Returns:
        question_json: A structured json array of questions from the DTOs
    """
    questions_payload = [dto.model_dump(mode='json', include=prompt_fields) for dto in dto_list]
    # rename id key to generic 'question_id' for prompt injection from the DTOs (syn_id or original_question_id)
    for question in questions_payload:
        question['question_id'] = (question.pop('syn_id', None) or 
                                   question.pop('original_question_id', None))

    questions_json = json.dumps(questions_payload, indent=2)
    return questions_json

# chunk questions by type and count
def chunk_by_type(dto_list: Sequence[DraftQuestion], chunk_size) -> list:
    """ 
    Group DTOs by question type and split each group into chunks.

    Args:
        dto_list: DTOs to chunk. Typed as Sequence (read-only) rather than list so
            subclass lists (e.g. list[LexDraftQuestion]) pass the type check;
            list is invariant, Sequence is not.
        chunk_size: Max questions per chunk.

    Returns:
        List of (question_type, chunk_index, batch) tuples.
    """
    # create a dict of each question type that defaults to empty list for each key  
    by_types= defaultdict(list)
    # populate the dict with question type as key, if q type not present = empty list
    for dto in dto_list:
        by_types[dto.question_type].append(dto)

    batches = []
    for question_type, dto_grouping in by_types.items():
        for i in range(0,len(dto_grouping),chunk_size):
            batches.append((question_type, i//chunk_size, dto_grouping[i:i+chunk_size]))

    return batches  # flat list of tuples: (question_type, batch_index, list[DraftQuestion]) for each batch       

def prepare_enrichment_prompt(questions_json: str, prompt_path:Path) -> str:
    """ """
    # get the prompt template location for the specific experiment run and read it
    prompt_template = prompt_path.read_text(encoding="utf-8")

    # Integrity checks for the prompt template from unit testing
    #1. incase the prompt template is empty
    if not prompt_template or prompt_template.isspace():
        raise ValueError(f"Prompt template file is empty: {prompt_path.name}")
    #2. if the prompt template doesn't have a placeholder for the chapters (source text)    
    if "{question_batch}" not in prompt_template:
        raise ValueError("Prompt template is missing the required '{question_batch}' placeholder.")

    # Prepare prompt: inject question batch 
    final_prompt = prompt_template.format(question_batch= questions_json)

    return final_prompt

# recover response
def convert_to_dto(parsed_responses: list[dict], 
                   draft_dtos_list: Sequence[DraftQuestion], 
                   specs: dict):
    """
    Build the next-tier DTOs from an LLM enrichment response.

    Pairs each LLM response record with its source DTO by question id, then constructs
    the complete output class from three sources: the response provides the new
    enrichment fields, the source DTO provides the core fields, and the specs dict 
    provides the pass configuration and metadata.
    
    Construction is the validation gate. A record that fails validation is set aside
    in the quarantine list with its error and the loop continues, so one bad record
    doesn't cost the rest of the batch. Other exceptions are left to propagate; they
    indicate a code or config problem (not bad data).

    Works for any enrichment pass — everything pass-specific comes from `specs`.

    Args:
        parsed_responses: LLM response records (already parsed from JSON). Each must
            carry `question_id` plus the fields for this pass.
        draft_dtos_list: The DTOs sent to the LLM for this batch. Typed as Sequence so
            subclass lists (e.g. list[LexDraftQuestion] for pass 2) pass the type check.
        specs: Pass config from ENRICHMENT_STRATEGY. Keys read here:
            - prompt_id: prompt version, stamped onto each output DTO
            - enrichment_fields: which fields to read from the response; anything else the
            LLM returned is ignored (originals always come from the source DTO)
            - output_dto: {QuestionType: class} — which DTO class to build per question type
            - enrichment_prompt_version_field_name: which DTO field the prompt version is
              written to, so each pass records its own version without overwriting the other

    Returns:
        (results, quarantine) — validated DTOs for this pass, and the records that failed
        construction as {"record": raw response, "error": message, "failure_mode": "dto_construction"}.
        The caller (flow) decides what the failure rate means.
    """
    # 1. take the DraftQuestion list and add a id_tag for lookup
    # TODO add conditionals for legacy handling here after happy path cleaered
    drafts_by_qid =  {d.syn_id: d for d in draft_dtos_list}

    # 2.  Build enrichment DTO with loop, for record in the returned responses,  
    results = []
    quarantine = []
    
    for record in parsed_responses:

        # 2.1. find the matching DraftQuestion DTO (from generation) using question, dict
        draft = drafts_by_qid[record['question_id']]
        # 2.2. take the new llm lex fields (dropping question id) as dict
        llm_fields = {k:v for k,v in record.items() if k in specs["enrichment_fields"]}
        # 2.3. compile into DTO model(by unpacking 2.1, 2.2) - model will ensure all fields are present and right type.
        # find question type
        q_type = draft.question_type
        dto_class = specs["output_dto"][q_type]
        try:
            updated_record = dto_class(
                **{specs["enrichment_prompt_version_field_name"]: specs["prompt_id"]},
                **draft.model_dump(), 
                **llm_fields)
            # 2.4. append dto to list.
            results.append(updated_record)
        # if the construction fails, quarantine record and log error, continue to next record    
        except ValidationError as e:
            quarantine.append({"record": record, 
                               "error": str(e),
                               "failure_mode": "dto_construction"})
            continue

    # 3. return tuple of (results dto list, quarantined llm response) 
    #    to the flow for further processing
    return results, quarantine

# TODO: persistence as parquet (for validation pipeline) for recovery / staging
def write_as_parquet():
    """Placeholder for future parquet write, for recovery / staging"""
    pass

# quarantine failed records for later inspection
def write_quarantine(entries: list[dict], run_id: str, configuration: dict) -> None:
    """
    One jsonl per run, appended per batch. Entries are self-describing via failure_mode.

    Args:
        entries: List of dicts containing the failed records, failure type tag, and their errors.
        run_id: Identifier for this pipeline run, used in checkpoint filenames.
        configuration: Pass config from ENRICHMENT_STRATEGY. Read here: `file_prefix` (checkpoint naming).
    """
    logger = get_run_logger()
    if not entries:
        return  # No entries to write

    # output_file = OUTPUT_DIR / f"{configuration['file_prefix']}_run{run_id}_quarantine.jsonl"
    output_file = build_run_artifact_path(OUTPUT_DIR,
                                          run_id,
                                          configuration['llm_pass'],
                                          QUARANTINE)
    
    for entry in entries:
        append_jsonl(entry, output_file)

    logger.warning("Quarantined %d records to %s", len(entries), output_file)

# Report for enrichment passes
# TODO: markdown report for enrichment passes — may fold into generation's report

## 3. ORCHESTRATOR

@flow
# for both enrichment passes (lexical and semantic), the flow is the same, only the config changes.
def enrich_with_llm_cols(run_id: str, 
                         dto_list: Sequence[DraftQuestion],
                         configuration:dict):
    """
    Run one LLM enrichment pass over a batch of questions.

    Chunks the input by question type, sends each chunk to the LLM, and builds the
    next-tier DTOs from the responses. Each batch is checkpointed to jsonl as it
    completes. Everything pass-specific comes from `configuration`, so the same flow
    runs both the lexical and semantic passes.
    
    Records that fail DTO construction are quarantined rather than failing the batch.
    Quarantine rates are logged per batch and at run closeout, and warn when they exceed
    the configured thresholds — monitored only, not enforced (see module docstring,
    Structural failure thresholds).

    Args:
        run_id: Identifier for this pipeline run, used in checkpoint filenames.
        dto_list: Questions to enrich. Must all be instances of the pass's input DTO.
        configuration: Pass config from ENRICHMENT_STRATEGY. Read here: `input_dto`
            (expected input class), `output_dto` (question types this pass supports),
            `prompt_file`, `file_prefix` (checkpoint naming), and the two failure-rate
            thresholds. Also passed through to the LLM call and to convert_to_dto.

    Returns:
        Tuple[List[EnrichedDTO], List[QuarantinedRecord]]: A tuple containing the list
        of enriched DTOs, and the list of quarantined records.

    Raises:
        ValueError: empty input; a question type with no output DTO configured; or the
            LLM response doesn't return exactly the question ids that were sent.
        TypeError: input DTOs don't match the pass's expected input class.
        
    ----
    TODO: consider frozen=True on DTO models to avoid mutation during enrichment passes.
          (each pass should build a new object, not edit the old one) - not needed right now.
           Not doing it now: some 'after' validators may assign to self, which frozen blocks.
           Would need to check those and re-run generation to confirm nothing breaks.    
    """
    # --- 0. SETUP ---
    # API and run config, call files (to save run reciept for LLM pass)
    logger = get_run_logger()
    configure_api(CONFIG_PATH)
    calls_file = build_run_artifact_path(RUNS_DIR, run_id,configuration['llm_pass'], CALLS)
    # token count of prompt template without attached questions
    template_token_count = measure_template_tokens(
        configuration['model_name'],
        configuration['prompt_file']
        )

    # --- 1. Initialization & Guards ---
    result_dtos = []
    all_quarantined = []  # records quarantined, across batches 
    total_processed = 0     # records returned by the LLM, across batches
    total_quarantined = 0   # records quarantined, across batches 

    # 1.1. validation checks
    # confirm question source DTO (jsonl for recovery / testing / legacy later)
    if not dto_list:
        raise ValueError("DTO list is empty. Cannot proceed with enrichment.")
    if not all(isinstance(dto, configuration["input_dto"]) for dto in dto_list):
        raise TypeError(f"All items in dto_list must be instances of {configuration['input_dto']} DTO type.")
    # fail-fast validation: if the question type is not specificied in the configuration,
    # raise an error for quick fix
    unsupported_qtype = {d.question_type for d in dto_list} - configuration["output_dto"].keys()
    if unsupported_qtype:
        raise ValueError(
            f"Question types not configured for this enrichment pass: {unsupported_qtype}"
            )

    # 1.2. chunk questions by type and count
    batches = chunk_by_type(dto_list, CHUNK_SIZE)

    # --- 2. Loop: for each batch ---
    for batch_index, (question_type, _, batch) in enumerate(batches): 
        # pacing for RPM limits — sleep before each call except the first
        # TODO: same limitation as generation — loop position is not time since
        # the last call. Proper fix is elapsed-time pacing inside make_api_call.
        if batch_index > 0:
            time.sleep(configuration.get("rate_limit_delay", 10))

        # 2.1. serialize dtos to json for prompt injection
        questions_for_prompt = serialize_dtos_to_json(batch, CORE_PROMPT_FIELDS)

        # 2.2. prepare prompt for enrichment pass
        prompt = prepare_enrichment_prompt(
            questions_for_prompt, configuration["prompt_file"]
            )

        # 2.3. API call
        try:
            response = make_api_call(prompt, configuration)
        except Exception as e:
            logger.error("Error occurred while making API call for batch %d of type %s: %s", 
                         batch_index, question_type, str(e))
            raise

        # 2.4. parse response into dict
        parsed_responses = json.loads(response.text)

        # 2.5.reconcile: all sent qids returned? no unexpected qids?
        sent = {d.syn_id for d in batch}
        returned = {r['question_id'] for r in parsed_responses}
        if sent != returned:
            raise ValueError(
                f"Mismatch in question IDs between sent batch and received responses "
                f"for batch {batch_index} of type {question_type}.")
        
        # 2.6. match response to existing record - combine and parse into output DTO
        draft_questions, batch_quarantined = convert_to_dto(parsed_responses, batch, configuration)
        #   quarantine records for batch and update total metrics
        all_quarantined.extend(batch_quarantined)
        total_processed += len(parsed_responses)
        total_quarantined += len(batch_quarantined)
        #   write quarantined records to jsonl for later inspection
        write_quarantine(batch_quarantined, run_id, configuration)
        
        #   quarantine threshold checks: (num quarantined / num returned) for batch
        batch_failure_rate = len(batch_quarantined)/len(parsed_responses) if parsed_responses else 0
        if batch_failure_rate > configuration["max_batch_failure_rate"]:
            logger.warning(
                "Batch %d (%s): %.1f%% structural failure rate exceeds %.1f%% limit (%d/%d)",
                batch_index, question_type, batch_failure_rate * 100,
                configuration["max_batch_failure_rate"] * 100,
                len(batch_quarantined), len(parsed_responses),
            )

        # 2.7.save response as jsonl for recovery / testing / legacy later
        #   2.7.1. write checkpoint file with enrichment results
        output_file = build_run_artifact_path(OUTPUT_DIR,
                                              run_id,
                                              configuration['llm_pass'],
                                              f"{question_type}_batch{batch_index}.jsonl"
)
        write_jsonl_checkpoint(draft_questions, output_file)
        #   2.7.2. accounting for API call
        token_breakdown = calculate_token_metrics(response, template_token_count)
        mode_counts = dict(Counter(q['failure_mode'] for q in batch_quarantined))
        
        #   build call_entry dict for run reciept 
        # (TODO refactor as helper later w. generation)
        call_entry= {
            'call_id': f"{question_type}_batch{batch_index}",
            'question_type': question_type,
            'model': configuration['model_name'],
            'prompt_version': configuration['prompt_id'],
            'output_file': output_file.name,
            'questions_saved': len(draft_questions),
            'tokens': token_breakdown,
            'quarantined': mode_counts,
        }
        # write call entry to jsonl file as receipt
        append_jsonl(call_entry, calls_file)

        # 2.8. append batch of output DTOs to results list
        result_dtos.extend(draft_questions)

    # 3. Closeout / return DTO results list ready for second enrichment pass

    #  3.1. quarantine threshold check: (num quarantined / num returned) for full run
    run_failure_rate = total_quarantined/total_processed if total_processed else 0
    
    #  3.2. status of llm pass
    status = "SUCCESS" if result_dtos else "FAILED"

    #  3.3: summary report for Prefect UI / terminal
    # save actual metrics of run for traceability (run "reciept")
    receipt_path = save_run_completion(
        PIPELINE_ID,
        run_id,
        configuration['llm_pass'],
        status,
        calls_file
        )
    # create run report
    create_run_report(receipt_path, OUTPUT_DIR)
    # completion update
    logger.info("🏁 %s Completed: %s", configuration['llm_pass'], run_id)
    
    # baseline record of run completion
    logger.info(
        "Run %s complete: %d/%d records quarantined (%.1f%%)",
        run_id, total_quarantined, total_processed, run_failure_rate * 100,
    )
    #  log warning if run failure rate exceeds threshold
    if run_failure_rate > configuration["max_run_failure_rate"]:
        logger.warning(
            "Run %s: %.1f%% structural failure rate exceeds %.1f%% limit (%d/%d)",
            run_id, run_failure_rate * 100,
            configuration["max_run_failure_rate"] * 100,
            total_quarantined, total_processed,
        )

    return result_dtos, all_quarantined

## 4. Run pipeline for testing / debugging
if __name__ == "__main__":
    try:
        test_id = f"test{datetime.now().strftime('%Y%m%d')}_{short_uuid()}" 
        results, quarantine_lex = enrich_with_llm_cols(run_id=test_id, 
                                    dto_list=retrive_dto_from_jsonl_file(test_path), 
                                    configuration=lex_config)
        synthetic_batch, quarantine_semantic = enrich_with_llm_cols(run_id=test_id,
                                            dto_list=results,
                                            configuration=semantic_config)
        print(synthetic_batch[0].model_dump_json(indent=2))
    except KeyboardInterrupt:
        # This catches Ctrl+C
        logger = logging.getLogger("prefect")
        logger.error("\n🛑 Pipeline execution aborted by user (KeyboardInterrupt).")
        print("\n🛑 User aborted execution via KeyboardInterrupt.")
        sys.exit(130) # Standard exit code for Script Terminated by Ctrl-C
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger = logging.getLogger("prefect")
        logger.error("\n💥 Pipeline crashed with critical error: %s", e)
        sys.exit(1)    
    # pass  # for testing / debugging in notebook or script context    
