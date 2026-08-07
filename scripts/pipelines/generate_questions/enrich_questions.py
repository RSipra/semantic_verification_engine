"""
Project: SVE (ref implementation: Harry Potter Trivia)
Automated Prefect pipeline: enrichment of generated questions.
======================================================================
Two LLM passes: (1) lexical enrichment, (2) semantic enrichment.

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
- Construction failure (critical null): quarantine.
- Abort thresholds: >10% of a batch, >5% of run.

Exit: SyntheticStandard set -> staging pool (GCS) or direct handoff to
validation pipeline. Semantic checks (grounding, dedup, RAG-triad) stay in
the validation pipeline; this module owns structural contract only.

>> Uses helpers from generate for now; refactor to common module after smoke test.

NOTE Timestamps: enrichment passes deliberately carry no timestamp of their own.
The record's `timestamp` is set at ingestion — generation for synthetic,
preprocessing for legacy — so both paths satisfy the model without a
source-conditional validator. Revisit only if enrichment becomes decoupled
from ingestion (e.g. backfilling a new field across existing records).
"""
## Setup
import json
from collections import defaultdict
from pathlib import Path
from prefect import flow, task, get_run_logger
from collections.abc import Sequence

from core.models import DraftQuestion, LexDraftQuestion
from scripts.pipelines.generate_questions.generate_questions import configure_api, make_api_call, CONFIG_PATH
from scripts.pipelines.generate_questions.prompts.pipeline_config import ENRICHMENT_STRATEGY
import notebook_support.notebook_config as nb_cfg

## 1. CONSTANTS, DTOs & CONFIGS
OUTPUT_DIR = nb_cfg.GENERATED_QUESTIONS_DIR
CORE_PROMPT_FIELDS = {'syn_id','question_type','question','answer','mcq_options'}

CHUNK_SIZE = 20     # number of questions per API call
LEX_PROMPT_PATH = nb_cfg.PROMPTS_DIR / "lex_enrichment_prompt_master_v0.txt"
lex_config = ENRICHMENT_STRATEGY["lex_enrichment"]
SEMANTIC_PROMPT_PATH = nb_cfg.PROMPTS_DIR / "semantic_enrichment_prompt_master_v0.txt"
semantic_config = ENRICHMENT_STRATEGY["semantic_enrichment"]

test_path = OUTPUT_DIR / "fr_questions_prisoner_of_azkaban_chapter_01_run20260724_9882e5b1.jsonl"

## 2. TASKS & HELPERS

# read jsonl from file into DTO
def retrive_dto_from_jsonl_file(file_path: Path):
    """"""
    with open(file_path, "r", encoding="utf-8") as f:
        return [DraftQuestion.model_validate_json(line) for line in f if line.strip()]
        
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
        question['question_id'] = (question.pop('syn_id',None) or 
                                   question.pop('original_question_id',None))

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

## 3. ORCHESTRATORS
## 3.1. Lexical enrichment (first pass)

# recover response
def convert_to_dto(parsed_responses: list[dict], draft_dtos_list: Sequence[DraftQuestion], specs: dict):
    """
    Build the next-tier DTOs from an LLM enrichment response.

    Pairs each LLM response record with its source DTO by question id, then constructs
    the complete output class from three sources: the response provides the new
    enrichment fields, the source DTO provides the core fields, and the specs dict 
    provides the pass configuration and metadata.
    
    Construction is the validation gate: if a record is malformed or incomplete,
    Pydantic raises here.

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
            - enrichment_prompt_version_col_name: which DTO field the prompt version is
              written to, so each pass records its own version without overwriting the other

    Returns:
        List of validated DTOs of the output class(es) for this pass.
    """
    # 1. take the DraftQuestion list and add a id_tag for lookup
    # TODO add conditionals for legacy handling here after happy path cleaered
    drafts_by_qid =  {d.syn_id: d for d in draft_dtos_list}

    # 2.  Build enrichment DTO with loop, for record in the returned responses,  
    results = []
    for record in parsed_responses:
        # 2.1. find the matching DraftQuestion DTO (from generation) using question, dict
        draft = drafts_by_qid[record['question_id']]
        # 2.2. take the new llm lex fields (dropping question id) as dict
        llm_fields = {k:v for k,v in record.items() if k in specs["enrichment_fields"]}
        # 2.3. compile into DTO model(by unpacking 2.1, 2.2) - model will ensure all fields are present and right type.
        # find question type
        q_type = draft.question_type
        dto_class = specs["output_dto"][q_type]
        updated_record = dto_class(
            **{specs["enrichment_prompt_version_field_name"]: specs["prompt_id"]},
            **draft.model_dump(), 
            **llm_fields)
        # 2.4. append dto to list.
        results.append(updated_record)

    # 3. return list of LexDraftQuestions
    return results

@flow
def enrich_with_lexical_cols(run_id: str, dto_list: list[DraftQuestion]):
    """ """
 
    # --- 0. SETUP ---
    # TODO: consider frozen=True on DTO models to avoid mutation during enrichment passes.
    #       (each pass should build a new object, not edit the old one) - not needed right now.
    #       Not doing it now: some 'after' validators may assign to self, which frozen blocks.
    #       Would need to check those and re-run generation to confirm nothing breaks.
    
    # API and run config
    configure_api(CONFIG_PATH)
     
    # --- 1. Initialization & Preprocessing ---
    results = []
    # 1.1. confirm question source DTO (jsonl for recovery / testing / legacy later)
    if not dto_list:
        raise ValueError("DTO list is empty. Cannot proceed with enrichment.")
    if not all(isinstance(dto, DraftQuestion) for dto in dto_list):
        raise TypeError("All items in dto_list must be instances of DraftQuestion.")
    batches = chunk_by_type(dto_list, CHUNK_SIZE)

    # --- 2. Loop: for each batch ---

    for question_type, batch_index, batch in batches: 
        # 2.1. serialize dtos to json for prompt injection
        questions_for_prompt = serialize_dtos_to_json(batch, CORE_PROMPT_FIELDS)
        # 2.2. prepare prompt for enrichment pass
        prompt = prepare_enrichment_prompt(questions_for_prompt, LEX_PROMPT_PATH)
        # 2.3. API call
        response = make_api_call(prompt, lex_config)
        # 2.4. parse response into dict
        parsed_responses = json.loads(response.text)
        # 2.5.reconcile: all sent qids returned? no unexpected qids?
        sent = {d.syn_id for d in batch}
        returned = {r['question_id'] for r in parsed_responses}
        if sent != returned:
            raise ValueError(
                f"Mismatch in question IDs between sent batch and received responses for batch {batch_index} of type {question_type}.")
        # 2.6. match response to existing record - combine and parse into LexDraftQuestion DTO
        lex_draft_questions = convert_to_dto(parsed_responses, batch, lex_config)
        # 2.7.save response as jsonl for recovery / testing / legacy later
        output_file = OUTPUT_DIR / f"lex_questions_run{run_id}_{question_type}_batch{batch_index}.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for dto in lex_draft_questions:
                f.write(dto.model_dump_json() + "\n")
        # 2.8. append batch of LexDraftQuestion DTOs to results list
        results.extend(lex_draft_questions)

    # 3. Closeout / return DTO results list ready for second enrichment pass
    return results

## 3.2 Semantic enrichment (second pass)
@flow
def enrich_with_semantic_cols(run_id: str, dto_list: list[LexDraftQuestion]):
    """ """
    # --- 0. SETUP ---
    # API and run config
    configure_api(CONFIG_PATH)
    
     # --- 1. Initialization & Preprocessing ---
    results = []
    # 1.1. confirm question source DTO (jsonl for recovery / testing / legacy later)
    if not dto_list:
        raise ValueError("DTO list is empty. Cannot proceed with enrichment.")
    if not all(isinstance(dto, LexDraftQuestion) for dto in dto_list):
        raise TypeError("All items in dto_list must be instances of LexDraftQuestion.")
    batches = chunk_by_type(dto_list, CHUNK_SIZE)
    
    # --- 2. Loop: for each batch ---
    
    for question_type, batch_index, batch in batches: 
        # 2.1. serialize dtos to json for prompt injection
        questions_for_prompt = serialize_dtos_to_json(batch, CORE_PROMPT_FIELDS)
        # 2.2. prepare prompt for enrichment pass
        prompt = prepare_enrichment_prompt(questions_for_prompt, SEMANTIC_PROMPT_PATH)
        # 2.3. API call
        response = make_api_call(prompt, semantic_config)
        # 2.4. parse response into dict
        parsed_responses = json.loads(response.text)
        # 2.5.reconcile: all sent qids returned? no unexpected qids?
        sent = {d.syn_id for d in batch}
        returned = {r['question_id'] for r in parsed_responses}
        if sent != returned:
            raise ValueError(
                f"Mismatch in question IDs between sent batch and received responses for batch {batch_index} of type {question_type}.")
        # 2.6. match response to existing record - combine and parse into SyntheticStandard or MCQ DTO
        semantic_draft_questions = convert_to_dto(parsed_responses, batch, semantic_config)
        # 2.7.save response as jsonl for recovery / testing / legacy later
        output_file = OUTPUT_DIR / f"semantic_questions_run{run_id}_{question_type}_batch{batch_index}.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for dto in semantic_draft_questions:
                f.write(dto.model_dump_json() + "\n")
        # 2.8. append batch of Synthetic Questions DTOs to results list
        results.extend(semantic_draft_questions)
    
    # 3. Closeout / return DTO results list ready for second enrichment pass
    return results

## 3.3 Run pipeline for testing / debugging
if __name__ == "__main__":
    results = enrich_with_lexical_cols(run_id="test1", dto_list=retrive_dto_from_jsonl_file(test_path))
    synthetic_batch = enrich_with_semantic_cols(run_id="test1", dto_list=results)
    print(synthetic_batch[0].model_dump_json(indent=2))
    # pass  # for testing / debugging in notebook or script context    
