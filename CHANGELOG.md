# Changelog

All notable changes to the "Harry Potter Trivia Engine" will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] (Current Work in Progress)
*Work targeting v0.2.2 release.*
### ACES Platform Implementation
- **Pipelines:** Implementing logic for the 4 core **Prefect** pipelines:
    - question_generation 
    - data_enrichment
    - qa_validation (with a vanilla SentenceBERT model)
    - ingestion
- **Data Lakes and storage:** Populating 1 datalake, 2 datasets with generated content following the **Medallion** pattern(Bronze -> Silver -> Gold).
- **Project Memory**: skeleton scripts

- **Goal:** Create the "Gold Level" dataset to close out this version.
- **Deliverable:** Fully operational Automated Content Creation and Enrichment System (ACES).
- **Deliverable:** A validated "Gold Standard" Trivia Dataset ready for the *Context Refinery* phase.

### Completed (Ready for Release)
- **Project Architecture:** Created architecture documentation for all project phases. Developed overall development schematics (showing data flow), detailed component architecture schematics (ACES), and infrastructure schematics (Game Cloud deployment).
- **Hybrid Data Management:** All data directories (except pipeline logs) are now managed with **DVC** (Data Version Control) backed by Google Cloud Storage (GCS). Pipeline logs (`07_pipeline_logs`) are maintained by Git.
- **Pipeline Script:** The `generate_pipeline` script is complete and ready for testing.

## [v0.2.3] - Planned (Milestone: Context Refinery)
*The "Semantic Intelligence" Upgrade.*
- Implementation of NER (Named Entity Recognition) for deeper metadata.
- Fine-tuning the Sentence-BERT model on the gold-level trivia dataset. 
- Production-ready dataset generation.
- updated ACES `qa_validation_pipeline` to utilize the fine-tuned SBERT model.

## [v0.2.4] - Planned (Milestone: Runtime Environment)
### Runtime Environment
*Live Game Demo*
- Docker containerization.
- Cloud deployment scripts.

## [v1.0.0] - Planned (Phase 2 Complete)
- First public deployment of the Trivia Game.
- Includes full fine-tuned Sentence-BERT integration.

---

## [v0.2.1] - 2025-11-23 (Milestone: Prompt Experimentation Complete)
*The transition point: Experimentation is done, and "content factory" starts.*
### Finalized
- **Prompt Engineering:** Completed all prompt experiments. Master prompts for EX, MCQ, and FR are frozen and ready for production.
- **Content generation:** Established the `generate_questions.py` skeleton and Prefect workflow structure (DAGs defined, but internal logic is WIP).
- **Project Packaging:** Added `pyproject.toml` to formalize the repository as a Python package.

### Added
- `src/ds_utils/schemas.py`: Defined strict TypedDict schemas for JSON outputs.
- `experiments.yaml`: Finalized configuration for the generation pipeline.

## [v0.2.0] - 2025-10-26 (Milestone: Phase 2 Kickoff)
*The clean slate start for the new Semantic Intelligence phase.*
### Added
- **Foundation:** Created skeleton folder structure for Prompt Engineering.
- **Prompt Strategy for generating questions with LLM** 
    - Defined key decisions (source content, number of questions, service provider)
    - Specified scope, constraints, and limits. 
    - Outlined overall methodology with mitigation strategies if duplicates generation across question types.
- **Source material**:
    - Created script `extract_hp_corpus` to download source materials with separate chapter `.txt` files.
    - Tested quality and completeness of source material for suitablity for grounding LLM.
- **Orchestration:** 
    - Setup cloud and api integrations for prompt experimentation.
    - completed `manual_api_call` to streamline api calls before automation for experiments.
    - prepared baseline `EX`, `MCQ`, `FR` prompt templates.
    - Initial setup of `eperiments.yaml`. 
    - Built the initial `run_experiments.py` script based on `manual_api_call`.

---

## [v0.1.0] - 2025-10-26 (Milestone: Phase 1 Complete)
*Foundation upgrade*
### Fixed
- **Improved readability**: Split monolith EDA notebook into 2 notebooks: `01_cleaning_and_eda.ipynb`, `02_eda_and_deduplication.ipynb`. Improved documentation and writeup.
- **Tokenizer upgrade**: Improved perfomance by:
    1. **Reordering processing order:** Moved lemmatization *before* stop word removal. This eliminated the bug where the tokenizer was dropping "did" before it could be converted to its base form "do" (an interrogative identifier).
    2. **Pronoun normalization:** Handled variations of "who" (whom, whose) to be grouped with "who" via post-processing logic rules.
- **Downstream workflow updated** to handle tokenizer upgrade.
    1. All downstream token-based features (question_type, TF-IDF, etc.) were regenerated to ensure data consistency. 
    2. **Automated semantic duplicate removal**:
        - updated methodology utiizes list of identified incomplete, incorrect, out-of-scope questions from v0.0 to be dropped immediately
        - automated semantic duplicate groups detection and selection of a rule-based "golden record"
        - Automated validation against v0.0 with override capabilities.

### Added    
- **Improved feature engineering**:
    - Expanded **Interrogative Keywords** to include auxiliary verbs for Y/N questions.
    - Upgraded binary `is_numeric` flag to a multi-class `answer_type` categorization.
    - Added length metrics (`question_length`, `answer_length`)
- **Organized project structure & refactored scripts**:  
    - Refactored  helper functions from the EDA notebooks (eda_scripts, new scripts)  into `ds_utils` library for SOC.
    - Standardized the project's directory structure (e.g., data/, scripts/, notebooks/, tests/).
    - Changed the standard data file format from .csv to .parquet to ensure data types (especially category) are preserved between sessions.
    - Centralized feature constants, categories, configurations into `ds_constants.py`
- **Data ingestion**: updated the `data_ingestion_pipeline()` method to handle new features.
- **Data Integration Logic**: Removed questions where `is_duplicate` flag is True from the append list and removed `is_duplicate` from the schema of `new_questions`.
- **UQA Methodology**: Defined a two-tiered approach with a future automated quantified QA scheme (composite quality scores). Finalized readability analysis of the baseline dataset. 

## [v0.0.0] - 2025-08-26 (Milestone: CLI-MVP Complete)
*Establish the Foundation.*
### Completed
- **EDA & Cleaning:** Full analysis of the source text complete.
- **CLI-MVP**: source code and unit testing complete.