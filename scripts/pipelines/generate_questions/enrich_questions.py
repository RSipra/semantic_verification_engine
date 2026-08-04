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

-- OUTLINE: (wip reference - to be removed once module structure in place)

- Define static dicts of cols for lexical prompt with instruction / description + format hints
- create LexDraftQuestion with factory
- prompt construction helper for new columns dict as SOT with assert on what is populated - used to 
  dynamically update the prompt and to define the requied fields for the LexDraftQuestion DTO.
- Take DraftQuestion DTO List and filter by question type and create batches x3 (DTO lists)
For each question type, batch number of questions:
- prepare prompt for first pass - passing only relelvant cols
- Make Api call x batches (use LLM service from src.engine.llm_service - if works will refactor 
  generate and move service to core)
- add new pass metadata (prompt version, model (if different from gen), etc)
- save responses as jsonl and construct LexQuestion DTO 
- assert all ids from DraftQuestion are in the LexQuestion
Next API call prep
- use DTOs to extract necessary cols for each batch for prompt prep - passing only relevant cols
- prepare prompt for second pass
- Make API call x batches
- save responses as jsonl and populate existing DTO
- Bronze pydantic gate validation before saving to staging pool GC or passing to validation pipeline directly as dto

- go through logic to handle failure modes. And batching logic - what is successful vs. not. 
~I have an adr for this.

"""
## Setup
import json
from collections import defaultdict
from pathlib import Path
from prefect import flow, task, get_run_logger

from core.models import DraftQuestion, LexDraftQuestion, SyntheticMCQ
from scripts.pipelines.generate_questions.generate_questions import configure_api, make_api_call, convert_question_to_dto, CONFIG_PATH
from scripts.pipelines.generate_questions.prompts.pipeline_config import ENRICHMENT_STRATEGY
import notebook_support.notebook_config as nb_cfg

## 1. CONSTANTS, DTOs & CONFIGS
 
LEX_PROMPT_FIELDS = {'syn_id','question_type','question','answer','mcq_options'}
LEXICAL_FIELDS = {"hint_1", "hint_2", "hint_3", "explanation", "answer_variations"}

CHUNK_SIZE = 20     # number of questions per API call
LEX_PROMPT_PATH = nb_cfg.PROMPTS_DIR / "lex_enrichment_prompt_master_v0.txt"
config = ENRICHMENT_STRATEGY["lex_enrichment"]
OUTPUT_DIR = nb_cfg.GENERATED_QUESTIONS_DIR

test_path = OUTPUT_DIR / "fr_questions_prisoner_of_azkaban_chapter_01_run20260724_9882e5b1.jsonl"

## 2. TASKS & HELPERS

# read jsonl from file into DTO
def retrive_dto_from_jsonl_file(file_path: Path):
    """"""
    with open(file_path, "r", encoding="utf-8") as f:
        return [DraftQuestion.model_validate_json(line) for line in f if line.strip]
        
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

def chunk_by_type(dto_list: list[DraftQuestion], chunk_size) -> list:
    """ """
    # create a dict of each question type that defaults to empty list for each key  
    by_types= defaultdict(list)
    # populate the dict with question type as key, if q type not present = empty list
    for dto in dto_list:
        by_types[dto.question_type].append(dto)

    batches = []
    for question_type, dto_grouping in by_types.items():
        for i in range(0,len(dto_grouping),chunk_size):
            batches.append((question_type, dto_grouping[i:i+chunk_size]))

    return batches        

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
def convert_to_lex_dto(llm_response, draft_dtos_list: list[DraftQuestion], prompt_verison:str):
    """"""
    # 1. load llm response.text (json) into a list of dicts
    responses = json.loads(llm_response.text)

    # 2. take the DraftQuestion list and add a id_tag for lookup
    drafts_by_qid =  {d.syn_id: d for d in draft_dtos_list}

    # 3. create metadata dict once (prompt version only right now)
    lex_prompt_version = prompt_verison

    # 3. Build Lex with loop, for record in the returned responses,  
    results = []
    for record in responses:
        # 3.1. find the matching DraftQuestion DTO (from generation) using question, dict
        draft = drafts_by_qid[record['question_id']]
        # 3.2. take the new llm lex fields (dropping question id) as dict
        lex_llm_fields = {k:v for k,v in record.items() if k in LEXICAL_FIELDS}
        # 3.3. compile into LexDraftQuestion (by unpacking 2, 3.1, 3.2) - model will ensure all fields are present and right type.
        updated_record = LexDraftQuestion(
            lex_enrich_prompt_version = lex_prompt_version,
            **draft.model_dump(), 
            **lex_llm_fields)
        # 3.4. append dto to list.
        results.append(updated_record)

    # 4. return list of LexDraftQuestions
    return results

@flow
def enrich_with_lexical_cols(dto_list: list[DraftQuestion]):
    """ """
    
    configure_api(CONFIG_PATH)

    for question_type, batch in chunk_by_type(dto_list, CHUNK_SIZE):
        
        prompt_questions = serialize_dtos_to_json(batch, LEX_PROMPT_FIELDS)
        prompt = prepare_enrichment_prompt(prompt_questions, LEX_PROMPT_PATH )

        response = make_api_call(prompt, config)
        
        print(json.dumps(json.loads(response.text), indent=2))

## 3.2 Semantic enrichment (second pass)

if __name__ == "__main__":
    
     
    # retrieve from jsonl in case DTOs are empty 
    questions = retrive_dto_from_jsonl_file(test_path)
    questions_for_prompt = serialize_dtos_to_json(questions,LEX_PROMPT_FIELDS)
    prompt = prepare_enrichment_prompt(questions_for_prompt, LEX_PROMPT_PATH)
    configure_api(CONFIG_PATH)
    response = make_api_call(prompt, config)
    lex_draft_questions = convert_to_lex_dto(response, questions, "v1")
    print(lex_draft_questions)
    