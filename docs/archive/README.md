#  Semantic Verification Engine 
### End-to-End system : &nbsp;&nbsp; Synthetic Data Generation → Context Layer → Runtime Application &nbsp;&nbsp;
**Building smart Q&A systems that don't hallucinate** *(under active development)*

![NLP](https://img.shields.io/badge/Advanced%20NLP-NER%20%7C%20SBERT-%236a0dad)
![GenAI Integration](https://img.shields.io/badge/GenAI%20Integration-Gemini%20API%20-%236a0dad)
![MLOps](https://img.shields.io/badge/MLOps-Prefect%20%7C%20DVC%20%7C%20Docker%20%7C%20GCS%20%7CVM%20-%236a0dad)
![Modular OOP](https://img.shields.io/badge/Modular%20Design-OOP-%236a0dad)

## What This Project Does
This is a **semantic answer verification system** currently demonstrated through a *Harry Potter trivia game* 🪄. It demonstrates AI system design where **correctness, latency, and cost predictability** are the key drivers (e.g. medical Q&A, compliance training, or certification exams). 

**The Core Problem:** Standard LLMs can hallucinate and drift. When you need very high accuracy and low latency, you can't rely on real-time generation.

**The Solution:** Separate heavy AI work (synthetic data generation, validation, enrichment) from runtime (answer verification). Generate high-quality content offline, serve it with CPU-only runtime optimized for fast, controlled interactions.

>#### ➡️ **Current State**:  Building a minimal end-to-end Phase 2 system, validating architecture and semantic logic as a working demo *(tracer build)*. 

### 👉🏼 [Try the Phase 1 MVP Demo ✨](https://34.27.245.64.sslip.io/)
**⚠️ Fair Warning:** This demo can be frustrating (scores were ~1~3 out of 10 in initial user testing despite correct knowledge). <br>
The MVP from the discovery stage deliberately showcases what breaks with naive approaches. Some of the key issues that surfaced:<br>

||**MVP issue**|**Root Cause**|**Solution**|**Phase 2 status**|
|-|-|-|-|-|
|1|*Frustrating UX with exact answer matching*|No semantic understanding|Tiered answer checking<br>*Direct → fuzzy → SBERT*|🚧 In progress (tracer implementation underway)|
|2|*Obscure / low-quality questions*|56% of raw dataset failed quality checks (1279 → 559 baseline records)<br> *Example: "|Insufficient quality and low coverage of core books.<br>Manual curation doesn't scale | Automated question generation & enrichment (Gemini API)|1. ✅ Prompt eng. complete<br>2. 🚧 tracer implementation underway  <br>3.🚧 Prefect pipeline undergoing testing|
|3|*Semantic duplicates bloat dataset*|Raw dataset had ~8% semantic near-duplicates (~100 questions)| Data quality issues in raw dataset (Hugging Face) discovered during EDA |Semi-automated cleanup script <br>(cosine similarity & graph analysis + golden record selection + manual review of ambiguous thresholds)| 1.  ✅ Legacy Baseline dataset (phase 1) cleaning complete <br>2. Tracer in progress 🚧 <br>(adapting Phase-1 script to SBERT for generated questions) |

**Examples from EDA and MVP:**
- **Issue 1**: [MVP walkthrough video, (00:55-01:19)](https://youtu.be/XXNDTiEgJYU?t=53)
- **Issue 2**: *Who lead the Gargoyle Strike? A group of wildcat Gargoyles.*
- **Issue 3**: *"Ever the eccentric, Dumbledore has a scar above his left knee that is a perfect map of what?"* vs. *"Dumbledore has a scar above his left knee that is a perfect map of what?"*

## ⭐️ The Semantic Verification Engine (SVE) Architecture

The platform is built around three core subsystems:

1. **Content Factory**: ingests raw text (Harry Potter books) and manufactures high-fidelity synthetic datasets using autonomous pipelines,
2. **Context Refinery**: A semantic processing and feature engineering layer with  that enriches the dataset with descriptive and contextual, thematic features.
3. **Runtime Environment**: an immutable (offline-capable) container that serves the game (and will later also host the local SLM).

[![The core demo implementation (Phase 2)](assets/docs/phase2/phase2_dev_main.jpg)](assets/docs/phase2/phase2_dev_main.jpg)
**Figure 1**: The main deployment specification. This schematic represents the backbone of the SVE project (click on figure for a closer view).

- **Architecture**: See the [Design Doc](docs/00_DESIGN_DOC_AND_ARCHITECTURE.md) for detailed data flow schemes for the *Content Factory* and *Runtime Environment*. It also provides the Basis for Design, architectural details for the other phases, and ADRs. 
- **Execution**: See the [Execution Plan](docs/01_EXECUTION_PLAN.md) for the Agile execution strategy for development.

### Why this Architecture?
| Design area | Typical failure mode | Design response in Project |
|-|-|-|
|Data Quality|Models can hallucinate or drift.|**Layered defenses**. Implemented a 3-tier quality strategy: *prevention* (schemas, prompts, grounding), *detection* (automated QA pipeline), and *correction* (adaptive acceptance sampling; user feedback at scale).<br>The QA pipeline enforces semantic deduplication, grounding checks to strictly gatekeep the *Gold* dataset |
|Unit Economics|API costs scale linearly.|**Fixed-cost edge serving**. Fixed API calls are decoupled from runtime in made in limited batches; fixed-cost local CPU container.|
|Reliability|LLMs represent probabilistic truth.|**Architectural decoupling & grounding.** <br>1. **Structural**: Decoupled runtime environment separates generation from consumption; Content Factory failures cannot crash the game.<br>2. **Semantic**: Content Factory logic forces strict source-text grounding, ensuring answers come from source books and not the model's training data.|
|Compute|Reliance on expensive GPUs.|**CPU-optimized delivery**: viably run game (later with a quantized SLM) on standard free-tier hardware|
|Operations|*Human-in-the-loop* needs slow scaling|**Autonomous ETL**.  Raw book text is automatically processed into high-quality structured JSON assets, removing the need for manual cleanup or curation.|
|Integration|Complex dependencies break systems.|**Immutable runtime infrastructure**. runtime system is a self-contained Docker artifact.|

## ⭐️  Key Differentiators

1. **The Content Factory**: The automated data generation and enrichment process has several benefits.
    - **Strategic compute allocation**: GenAI is used only for high-value batch processing instead of expensive realtime queries.
    - **Extensible enrichment framework**: The system is designed to support modular expansion without structural refactoring. New attributes, such as persona-driven hints or trivia fun facts, can be added incrementally to existing records with the proposed enrichment pipeline. All feature additions flow through a single, governed ingestion path to the Gold Dataset, preserving data integrity and semantic consistency as the system evolves.
    - **Dual-product generation**: Creating the game content (trivia dataset) with the Content Factory can also be used to produce the *instruction-tuning corpus* for future SLM integration. Tone, persona, and response style are specified directly in the pipeline schemas and manifests. This enables zero-cost *style distillation* so the AI Persona tone naturally matches the content without separate labeling or post-processing.
2. **Hybrid Intelligence Architecture**: 
    - **High perceived intelligence / low compute**: in the final envisioned design (phase 3), the runtime decouples knowledge (dataset) from reasoning (SLM acting as both Persona and Judge). This uses knowledge distillation (Teacher-Student training) to ensure the small model mimics the wit and logic of a large LLM without the compute cost.
    - **No hallucination at runtime**: by retrieving answers from disk rather than generating using GenAI API calls at runtime. This avoids cases where the model produces responses that *sound* correct but are factually wrong (e.g. a plausible-sounding but nonexistent Harry Potter question).

## Real world applications

The architecture can be generalized from a trivia game to a domain-agnostic *semantic verification engine*. It solves the problem of last mile knowledge delivery by taking dense, static documentation (e.g. pdfs, wikis, manuals) and converting it into an interactive, gamified mastery tool. Some example use cases:

Use Case|Input|Output|Why It Wins|
|-|-|-|-|
|MCAT Prep|Medical textbooks|Quiz with verified answer keys|LLMs hallucinate drug dosages. This uses dataset lookups|
|Safety Training|Company safety manuals|Certification quiz (offline-capable)|Deploys to 10,000 employees for fixed cost. No API charges.|
|Product Training|Technical spec sheets|Sales team practice questions|Turn 50-page PDFs into interactive quizzes in hours|

## Technical Deep-Dive

### What's Already Working (Phase 1)
✅ VM + Docker deployment — Live at https://34.27.245.64.sslip.io/<br>
✅ Parquet Legacy knowledge base — verified, immutable artifact for next phase.<br>
✅ MVC game architecture — modular Python code unit tested with pytest<br>
✅ Exact string matching — Baseline logic (intentionally fragile)

<details>
<summary><i>Click to expand Phase 1 data science & MVP metrics</i></summary>

### Phase 1 focused on discovery & prototyping
The raw dataset was manually curated and standardized to build the Baseline (v0) dataset. This manual process exposed the scalability bottlenecks that directly informed the [Content Factory architecture](docs/00_DESIGN_DOC_AND_ARCHITECTURE.md#p2-content-factory-architecture-in-depth) for Phase 2.

|Metric|Value|Description|
|-|-|-|
|Data Optimization|1279 → 902|Aggressive pruning (Q-Q cosine similarity) + Strategic Enrichment (100+ new explanatory items, 240+ rehabilitated)|
|Topic Diversity|86% unique|Answer-Answer (A-A) analysis confirmed high semantic variety, limiting repetition to core entities.|
|Taxonomy (interrogative identifier)|100%|Achieved complete categorization coverage using a custom tokenizer & lemmatization script. This is important because it is used to classify questions into the main types (Explanatory, Factual-Recall, Mulitple-Choice, Yes/No)|
|Class Balance|Baseline_v0 dataset|78% Factual Recall, 11% Explanatory, 10% MCQ, 1% Yes/No.|
|Schema Validation|	Pass	|Ingestion script with standardized schema checks, automated deduplications minimized error when appending to the main dataset|
|Game Core|	MVP	|Python MVC (Model-View-Controller) Architecture w/ pytest coverage|

#### Key Analytical Insights
* **Linguistic fingerprint:** Answer length can be used to distinguish between Explanatory (EX) from other short-answer types (FR, MCQ, YN). The [boxplot analysis](#c-box-plot-of-answer-length-vs-question-type-baseline-v0-dataset) shows the the interquartile range for EX answers (8-22 words) does not overlap with FR, MCQ, or YN.
    * *Architectural Implication:* Phase 2 monitors answer-shape patterns as the dataset grows to preserve consistency across question types. See [ADR-P2-014](docs/adrs/ADR-P2-014.md) for the full rationale and monitoring approach.
- **Vector drift**: The TF-IDF vectorizer struggled with the vocabulary shift introduced by new *explanatory* (EX) questions, directly motivating the switch to Sentence-BERT (SBERT) for Phase 2 deduplication.
- **Question-type imbalance**: The baseline dataset was heavily skewed toward Factual Recall (78%). This imbalance drove the requirement for the Phase 2 *Content Factory* to synthetically generate complex "Why/How" questions. These type of questions are key differtiators for the game experience. It should also be able to generate the other question types to keep dataset in balance.

#### Architecture emergence (Learnings)
The Phase 2 Content Factory Medallion structure (Bronze / Silver / Gold) was not pre-planned; it emerged as a solution to the bottlenecks discovered during Phase 1:

|Layer|Phase 1 Discovery (The Problem)|Phase 2 Solution|
|-|-|-|
|Bronze<br>(Generation)|Manual curation of raw dataset required deleting 57% of data due to quality issues (duplicates, errors)|LLM model (Gemini): add synthetic high-quality question generation via the `question_generation` pipeline, also allows balancing question type variety. Legacy data is enriched once with an LLM to match the defined Bronze schema.|
|Silver<br>(Validation)|Simple string matching failed to catch semantic duplicates (phrasing variations) causing bloat.|Semantic gates (SBERT): Decoupled validation into a `qa_validation` pipeline using Sentence-BERT for semantic deduplication and hallucination checks.|
|Gold<br>(Ingestion)|Validation and ingestion scripts were tightly coupled which would be difficult to manage as more validation logic is added.|Lightweight ingestion: Separated final commit logic into a `data_ingestion` pipeline, ensuring only "gold-grade" data is versioned (DVC) and transition point to the next subsystem (Context Refinery)|

#### Phase-1 Visual Artifacts

1. **Interrogative keyword distribution (100% coverage)** 
    <details>
    <summary><b>🔎 View the keyword distribution plot</b></summary>

    [![Interrogative keyword distribution](assets/docs/phase1/p1_keyword_graph.png)](assets/docs/phase1/p1_keyword_graph.png)
    *(Click image to open full resolution)*
    </details>
    <br>

2. Baseline v.0 dataset status map 
    <details>
    <summary><b>🔎 View Baseline v0 Status Map</b></summary>

    [![Baseline Dashboard](assets/docs/phase1/p1_baseline_v0_statusmap.png)](assets/docs/phase1/p1_baseline_v0_statusmap.png)
    *(Click image to open full resolution)*
    </details>

3. **Box plot of Answer Length vs. Question type (Baseline v.0 dataset)**
    <details>
    <summary><b>🔎 View the keyword distribution plot</b></summary>

    [![Boxplot: Answer len vs. question type](assets/docs/phase1/p1_baseline_v0_boxplot_ans_len.png)](assets/docs/phase1/p1_baseline_v0_boxplot_ans_len.png)
    *(Click image to open full resolution)*
    </details>

**Refer to [details section](#want-to-dive-further) to see key artifacts (EDA, deduplication notebooks)**
</details>

### What's Being Added (Phase 2)

#### 🚧 Automated Content Factory (in active development)

1. **Automated Prefect-orchestrated question generation pipeline** (undergoing testing): generates high-quality questions from Harry Potter source text.

    **📓 Want to run this yourself?** A demo notebook (*coming soon*) will let you generate questions from a single Harry Potter chapter. Meanwhile, explore the [**full pipeline code**.](scripts/pipelines/generate_questions/generate_questions.py)

2. **Quality Gates (Pydantic V2):**
Questions must pass strict schema validation before it is upgraded to the next data tier (example code snippet):
    ```python
    # Base schema — all question types inherit core fields
    class BaseQuestion(BaseModel):
    """
    The foundational schema defining fields common to all trivia question types.
    
    All specific question formats (Standard, MCQ) inherit from this structure
    to ensure core data is always present.
    """
    question_type: QuestionType
    question_source: QuestionSource
    question: str = Field(..., min_length=1)  # ensure not empty str
    answer: str = Field(..., min_length=1)
    answer_variations: List[str]  # acceptable alternative phrasings
    hint_1: str = Field(..., min_length=1)
    hint_2: str
    hint_3: str
    explanation: str = Field(..., min_length=1)
    semantic_entity_refs: List[str]
    semantic_lore_concepts: List[str]

    # Schema registry — routes validation by data origin and data tier
    # e.g. VALIDATION_REGISTRY[QuestionSource.SYNTHETIC][DataTier.BRONZE] → SyntheticBronzeQuestion
    VALIDATION_REGISTRY = {
        QuestionSource.LEGACY:{DataTier.BRONZE:{...}, DataTier.SILVER:{...}, DataTier.GOLD:{...}},
        QuestionSource.SYNTHETIC:{
            DataTier.BRONZE:{
                QuestionType.EX : SyntheticStandard,
                QuestionType.FR : SyntheticStandard,
                QuestionType.MCQ: SyntheticMCQ
            },
            DataTier.SILVER:{...},
            DataTier.GOLD:{...}
            }
    }

    # Validation router — selects correct schema for source + tier combination
    def select_pydantic_scheme(question_source: QuestionSource, data_tier: DataTier) -> dict:
        """Routes to the correct schema based on data origin and medallion tier"""
        return pyd.VALIDATION_REGISTRY.get(question_source,{}).get(data_tier,{})
    ```
## Why this project?
This project is a learning accelerator. I compressed multiple skill domains (DS, MLOps, System design) into one system to see how they interact.

**The meta-goal**: Coming from a chemical engineering background, I have seen the value of rigorous upfront design in high-risk systems, but I am also aware of its limitations (rigidity, slow feedback). This project deliberately plays with that tension to demonstrate how disciplined systems thinking can *support* fast, iterative delivery rather than compete with it.

### Want to dive further?
| | Data Scientists | ML Engineers |
|-|-|-|
| **Start** |[EDA Notebook](notebooks/02_research/01_cleaning_and_eda.ipynb) — cleaning, n-gram analysis, patterns<br> [Deduplication & Processing](notebooks/02_research/02_eda_and_deduplication.ipynb) - semantic similarity, feature engineering| [Design Doc](docs/00_DESIGN_DOC_AND_ARCHITECTURE.md) — architecture, ADRs, trade-offs |
| **Then** |[Prompt engineering experiments](notebooks/02_research/03_aces_generating_new_questions/) - strategy, LLM selection, model parameter and token assessments|[Pipeline scripts](scripts/pipelines/) — Prefect orchestration|
| **Deep dive** |[Data Validation Notebook](notebooks/02_research/07_qa_validation_v0.ipynb) - SBERT for grounding and duplicate checks |[Game source code](src/HPtrivia_game/) — modular Python, MVC, pytest|

## 🛠️ Project Status

This project follows a data-centric AI lifecycle. Development is currently in Phase 2 (adding semantic intelligence), having completed phase 1 (discovery and foundation). Refer to [workflow](docs/01_EXECUTION_PLAN.md) for the sprint breakdown.

**✅ Phase 1: Data Science Discovery & Game Foundation &nbsp;&nbsp;&nbsp;[COMPLETE]**<br>
Completed EDA, schema definition, and CLI-MVP development. 

**🚧 Phase 2: Operationalize core design &nbsp;&nbsp;&nbsp;[ACTIVE]**<br>
Create the design operational backbone (all three subsystems: Content Factory, Context Refinery, Runtime Environment) leveraging phase 1 components and learning.
 Building a minimal end-to-end system across all three subsystems. Key progress:

- ✅ Prompt engineering complete (validated generation quality) 
- 🚧 Tracer build in progress (end-to-end skeleton connecting all subsystems):
    - ✅ Tracer sample dataset complete  (strategically sampled to stress system design: 104 Legacy + 50 Synthetic [FR, EX, MCQ]).
    - 🚧 Validation logic in development.
    - 📋 Semantic answer matching (SBERT) — pending.
- 🚧 Prefect `question_generation` pipeline testing.

## 🛠️ Tech Stack
The following stack represents the technology used in active development. 
- **Runtime**: Python 3.12 (game), Google Cloud VM with TailScale, Parquet (data).
- **AI & Semantics**: Google Gemini 2.5 Flash, SBERT, NLTK
- **MLOps**: Docker, Prefect, Pydantic, DVC (Data Version Control)

See [requirements.txt](requirements.txt) for packages required to run the game, and [requirements-dev.txt](requirements-dev.txt) for the complete list of tools used in the game as well as notebooks, data processing, and advanced NLP work.

💡 **Development Note**:  This project was built with LLM support (Gemini/ChatGPT) acting as thought partners for system design reviews, documentation refinement, and technical guidance. 

## ℹ️ Data Sources

For more information on the datasets and all other data types used, please refer to the [Data_Sources.md](DATA_SOURCES.md).

## ℹ️ License

This project's code is licensed under the [MIT License](LICENSE-MIT). See the [MIT License](LICENSE-MIT) file for details.

<details>
<summary><b>Data usage</b></summary>

- *Raw Inputs*: The original raw trivia data used for Phase 1 baseline testing is documented in [Data_Sources.md](DATA_SOURCES.md) and is not redistributed in this repository.
- *Gold Dataset*: The runtime database is a hybrid asset. It consists of the original source data (cleaned, normalized, and validated) augmented with synthetic content and metadata generated via the Content Factory. To respect original copyrights, the full gold dataset is not included in this repository.

</details>

## ℹ️ Disclaimer:
This project is an unofficial fan tribute to the Harry Potter series and is not endorsed by or affiliated with J.K. Rowling, Warner Bros., or any related parties. It is a passion and learning project created solely for educational and non-commercial purposes.