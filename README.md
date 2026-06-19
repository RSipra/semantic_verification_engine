![NLP](https://img.shields.io/badge/%20NLP-NLI%20%7C%20SBERT-%236a0dad)
![GenAI Integration](https://img.shields.io/badge/GenAI%20Integration-Gemini%20API%20-%236a0dad)
![MLOps](https://img.shields.io/badge/MLOps-Prefect%20%7C%20DVC%20%7C%20Docker%20%7C%20GCS%20%7CVM%20-%236a0dad)

#  Semantic Verification Engine (SVE)
### Constrained AI architecture for accurate, low-latency semantic evaluation  

> [!TIP] 
> TL;DR: **An interactive trivia game with a smart answer-checker that understands free-form, paraphrased answers** *→ lean and fast because expensive LLM calls are made only where they add value.*
>
>This comes down to design, where the LLM is used in two distinct roles: 
> - **Generates the dataset (offline):** an automated pipeline uses the LLM’s creativity to generate questions from book text, followed by layered validation to filter for quality. This allows fast, large-scale generation with consistent results that is much harder to do manually.
> - **Evaluates answers (online):** fast, tiered checks resolve ~2 in 3 answers locally in under 150ms with lightweight checks, and escalates the hard ones to the LLM, for 85%+ accuracy overall - so the results feel fast and fair.
>
>**The trade:** a deep, quality-checked, reusable dataset and a lean runtime in exchange for less dynamic runtime behaviour. Interactions (hints, explanations, feedback) are pre-generated. This fits a structured game since it doesn't need open-ended conversations like a chat.
> 
> **The payoff**: game responses are faster, more predictable. The system is cheaper to scale; it can add more runtime copies as demand grows while the LLM usage remains deliberate and controlled (reducing potential for runaway API costs).
>
>- **Built end-to-end by a single developer**: data generation, validation, NLP, evaluation, the live game app, and containerized cloud deployment.
>- **Stack:** &nbsp;&nbsp; Python · SBERT · NLI · Gemini · Pydantic · Prefect · Docker · Google Cloud
>
> **[▶ ✨Play the live demo ✨](https://34.27.245.64.sslip.io/)** → the fastest way to see it work *(best played on desktop, game load is ~30s while models warm up)*.
>


## What is the SVE?

The **Semantic Verification Engine (SVE)** is a smart trivia game at its core. It does two main things: it generates and validates its own high-quality dataset from source text at volume, then serves it in an interactive Q&A session where players can give free-form answers.

A trivia game sounds simple but doing it well surfaces a harder problem: verifying natural-language answers accurately. This means understanding what the player is trying to say even when it’s paraphrased, partial, or underspecified. Players can use shortcuts, nicknames, or domain-specific references (e.g. “muggles”) that only make sense in context. Answers can also vary between short, factual recall to long and explanatory. Essentially, the system has to interpret player intent under tight engineering constraints.

⛯ *Example use cases: educational games, certification practice, employee training, and other knowledge-retention systems*.

In such applications, reaching for an LLM is reasonable. But under constraints such as cost, performance, or task simplicity, defaulting to it can be inefficient.  For simpler answers, an expensive, powerful model is overkill and adds latency it doesn't earn. It can also hallucinate when generating domain-specific content on the spot, unchecked. Its real value is on open-ended, explanatory answers that simpler methods can't reliably verify. 

So the design approach is to understand the key requirements and then fit the semantic tooling (including LLM) to them. This led to the core design concept:

>*Move the expensive LLM work offline and compile it into validated, reusable assets. The runtime only serves those assets so it can stay lean, fast, predictable, and cheap to scale.*

At runtime, SVE acts as a semantic evaluation layer, checking whether a user's answer is correct with progressively more sophisticated verification methods. The intelligence needed to support that evaluation is prepared offline through data generation, validation, and enrichment workflows.

---
► [✨**Live Demo**✨](https://34.27.245.64.sslip.io/) &nbsp;|&nbsp; [Tracer Implementation Walkthrough](notebooks/01_demos/01_tracer/README.md) &nbsp;|&nbsp; [Design Doc & ADRs](docs/00_DESIGN_DOC_AND_ARCHITECTURE.md) &nbsp;|&nbsp; [Execution Plan](docs/01_EXECUTION_PLAN.md) &nbsp; <br>⚠️ *Note:  the MVP demo can take ~30s to load transformer models at the start - appreciate your patience* 😄

---

## Runtime Constraints (Tracer MVP)

The runtime environment has the tightest constraints that drive the system design. The [Basis for Design (BoD)](docs/00_DESIGN_DOC_AND_ARCHITECTURE.md#15-basis-for-design) formalizes these constraints into boundaries the system must operate within and targets it should meet.

A tracer (minimum end-to-end build that exercises each subsystem) confirmed the logic and architecture work before automation is added. Fine-tuning of thresholds and optimizations will be done once the logic is stable (tracer corrections implemented).

The Tracer CLI-MVP column reflects what actually emerged from meeting those requirements in practice: some constraints were anticipated, others surfaced through deployment.

The constraints are iteratively refined as the telemetry from the tracer is collected.

| Constraint |BoD Requirement |Tracer CLI-MVP |
|-|-|-|
| Economics | Minimum-cost operation and minimize per-query API cost at runtime (near-zero)|GCP e2-micro (free-tier); zero runtime API cost (free-tier).<br> Public demo HTTPS ~$11/month; security infrastructure cost emerged at deployment, within $20 contingency threshold |
| Performance|Local inference < 500ms p95;<br> LLM escalation < 1–2s p95;<br> gameplay feels smooth |CPU-only Docker runtime on e2-micro (2 vCPUs, 1 GB RAM, 30GB storage);<br>local inference prioritized to minimize LLM dependency; ongoing collection of runtime latency|
| Quality |No hallucinations at runtime;<br> evaluators correctly distinguishes correct from incorrect answers| Zero generation at runtime; pre-validated Parquet assets. <br>Evaluator accuracy ≥ 85% (85–93% observed in notebook testing; runtime measurement pending) |
| Capacity |5–10 concurrent users within free-tier cost limits | GoTTY + Docker on GCP e2-micro; single-session in practice; GoTTY shares one terminal rather than managing independent sessions; 5–10 concurrent user target requires the planned FastAPI service layer|
| Scalability|Unit cost constant or decreasing as content volume grows | Offline intelligence layer; minimal AI cost per query; <br> planned FastAPI service + containerised deployment enables horizontal scaling with load balancing; ceiling determined by SBERT CPU compute ceiling, VM cost beyond free tier, and LLM API rate limits |

## The System Design

> **Project Status**: **Phase 2 tracer build completed and runtime MVP deployed.** End-to-end flow validated across all three subsystems. Runtime performance and generation quality metrics are being actively collected.

The full system design consists of three subsystems:

1. **Content generation (offline)**: Prefect-orchestrated pipelines ingest raw source text and produce structured, validated trivia content. Questions are generated by LLM-based multi-prompt enrichment grounded in the source text.

    The validation pipeline then checks generated records for structural and contextual correctness (e.g. LLM judge with RAG-Triad). The pipeline also precomputes SBERT embeddings for core fields to support offline semantic deduplication and runtime evaluation. Tiered Pydantic gates enforce progressive quality checks: Bronze (staging), Silver (validated system of record), and Gold (curated projection for downstream subsystems).

    The two pipelines work in tandem. Generation is creative and diverse, while validation stays strict. Validation removes questions that still fall short, protecting the quality of the Silver dataset, and in turn the runtime, to preserve user trust and game reputation.
   - **Tracer status**: end-to-end logic confirmed in notebooks; Prefect automation in progress.
2. **Context enrichment layer (offline)**: The context refinery will enrich generated questions with structured semantic features stored as dataset columns. These features are intended for reuse across downstream tasks.
    - **Tracer status**: descriptive feature logic confirmed; NER and other contextual features deferred to next stage.
3. **Runtime environment (online)**: A Docker container serving the game from validated, immutable Parquet assets. Evaluation is layered: exact match → fuzzy match / structured rules → SBERT semantic similarity → LLM escalation. The container has no runtime dependency on the upstream systems.

    The offline precomputation keeps runtime work minimal. SBERT embeddings are computed ahead of time and tensors are hydrated at startup, so during live play only the player's answer needs embedding.
    - **Tracer status**: deployed and live.   

[![The core demo implementation (Phase 2)](assets/docs/phase2/phase2_dev_main.jpg)](assets/docs/phase2/phase2_dev_main.jpg)
**Figure 1**: Design overview. This schematic represents the backbone of the SVE project (click on figure for a closer view).

Refer to the [*Design Doc and ADRs*](/docs/00_DESIGN_DOC_AND_ARCHITECTURE.md) for further details on architecture.

#### Reference Implementation
The SVE architecture is domain-agnostic. 
The underlying system solves a generalizable problem: converting dense, static knowledge into accurate, interactive, and auditable delivery at low cost.

- *Validation layer:*  The Harry Potter interface serves as the reference implementation and test surface. <br>
- *Why?* The series was chosen because it is a bounded knowledge domain, widely recognized, with a well-defined scope. Together this gives objective validation criteria for assessing the project. It retains many of the language evaluation challenges from larger domains, keeps focus on system behaviour, while remaining accessible and fun! 🧙🏼‍♂️ 
- *Generalization*: Applying SVE to a regulated domain, such as clinical Q&A, compliance training, or financial certification, would require stricter controls at specific layers. The requirements can be accommodated without structural redesign through configuration, enhanced validation, and policy controls.

## Tracer MVP Implementation 
The runtime is modular Python in [src/](/src/).  Notebooks are used for research, validation, and demonstrations.
- [src/core](/src/core/): shared components used across offline pipelines, runtime evaluation, and notebooks that includes schemas, SBERT embeddings, and utility functions.
- [src/engine](/src/engine/): evaluation layer that handles routing and scoring logic. Includes the task router, tiered evaluators, DTOs, LLM interface, and tensor hydration at warmup for embedding models.
- [src/game_app](/src/game_app/): application layer that implements the user-facing game flow, including session management, controller logic, and view rendering.

The [tracer walkthrough demos](/notebooks/01_demos/01_tracer/) run against these modules to validate the end-to-end system behaviour.

## Preliminary Runtime Metrics
>⚠️ First-pass results: single batch, 13 sessions. Tracer dataset was intentionally composed to stress system design (high Explanatory question share). Figures will shift as session diversity and batch count increase. Do not treat as a stable baseline.

### Evaluation tier routing

|Resolution Tier| Questions Presented* | Share|Notes
|-|-|-|-|
|Exact match|30|26%|-|
|Fuzzy match|10|9%|-|
|SBERT semantic|40|35%|-|
|LLM escalation|35|30%|-|
|Unresolved|1|<1%| empty submission|

- *Note*: Sessions can end early if a player runs out of chances, so not all session questions are presented.

*Local inference resolution rate*: **69% of questions resolved without an LLM call**. The tiered cascade working as designed with significant portion of answers settled with local checks.

### Latency
The offline/online split delivers on the fast path: local inference averages 62ms (150ms p95), comfortably under target. The slower tail is LLM-driven by design — isolated to the hard answers, not the common case.

Primarily determined by the LLM API call.
|Path|Average|P95|Notes|
|-|-|-|-|
|Local inference with SBERT|0.062s|0.15s (150ms)|Meets local p95 < 500ms target|Fast path; min observed: 0ms|
|LLM escalation|2.6s|7.1s|Above target; high EX question share inflates this, max: 33s|
|Overall evaluation|2.6s|9.9s|LLM path driven; p95 above 5s UX fallback. LLM evaluations include a 6s cooldown to manage RPM limits| 

- **Free-tier penalty**: shifting to paid-tier will shrink the required cooldown time needed between requests. Currently the free-tier requires 6s cool down, resulting in an evaluation latency of ~7s even if the LLM call itself took ~1 to ~2s. Game play is still smooth because player reading evaluations and moving to the next question absorbs cool down time. Can consider dynamic cooldown within Controller.
<!--- optimizations for later stages.-->

### Compute
- primarily determined by SBERT local inference.
- Measured via `docker stats` over a single session (8min window ≈ 1 session) on a GCP e2-micro (0.25 vCPU baseline, 2 vCPU burst, 1GB RAM).
- SBERT operates as a burst workload, near-zero CPU at idle with short spikes during inference. No CPU throttling observed at current level.

| Metric | Value |
|---|---|
| Idle CPU | 0.61% |
| Inference CPU (mean) | 54.41% |
| Inference CPU (max) | 83.55% |
| Memory (idle) | ~367 MB |
| Memory (loaded) | ~447 MB |

### Bottlenecks Identified
- Loading models in startup leads to a 30s lag before gameplay begins. This persists even after the initialization sequence was broken up and SBERT loading and its warmup are handled after introduction with a UX loading screen. Will be handled when shifting to Fast API - will have a singular startup with container and keep it warm to avoid coldstart with every game start. <!--Likely caused by the pydantic validation upfront after tensor addition - but need to test-->
- Could not run on 10GB, docker build failed, not enough temporary cache for installation requirements. Increased VM storage to 30 GB.
- LLM latency is highly variable. Generally within the required range but can jump to ~22 to ~35 seconds. Mitigations include reducing LLM fallback with improved local inference, shifting to paid-tier (less cool down to manage RPM usage limits) and can be managed with self-hosting a model as a service if / when scale justifies.
- Explanatory answers contain  multiple implicit claims that SBERT similarity alone cannot reliably verify, routing them to the LLM judge by default. Primary driver of the 30% LLM routing share. Planned improvement: decompose long answers into atomic claims verifiable locally via SBERT / NLI, reducing LLM fallback and improving the shift-left resolution rate. NLI is implemented in evaluator but will come online with claims breakdown. 

## Offline Data Generation & Validation Results (Tracer)

#### Generation pipeline

- A total of 50 questions were generated from 6 chapters.
- Repeated runs over chapters for different question types generated: Factual Recall (FR) x 16 / Multiple choice (MCQ) x 18 / Explanatory (EX) x 16 questions.
- Pipeline consists of one generation pass, two enrichment passes to augment core fields for in-game intelligence (hints, explanation, answer variations, semantic entity references, and core lore concepts).

#### QA and Validation pipeline
This is the final quality gate; everything downstream is additive and builds on what passes. So strictness here lets later stages trust the data without re-validating it.
- *Yield:*  **35 out of 50 questions (70%)** were promoted to Silver tier. 
- The largest drop is because of intra-batch deduplication. These duplicates occur when the generator centers different question types on the same salient detail (trivia kernel) from source text.
- The table below shows the breakdown by pipeline stage:

| Validation Check | Passed | Failed / Dropped |
|---|---|---|
| Structural validation against Silver schema (Pydantic) | 50 | 0 |
| Intra-batch semantic deduplication (across question types) | 44 | 6 |
| Contextual integrity (RAG-Triad): consistency check between source quote, question, answer * | 42 | 2 |
| Alignment of answer variations to core fields (question, answer) | 38 | 4 |
| Alignment of MCQ options and LLM categorization to core fields| 36 | 2 |
| Canonical semantic deduplication (of batch against main Silver dataset)|35|1|

The RAG-Triad contextual check is validated at tracer scale; scaling it for the full system is an open design question - see [ADR-P2-020](/docs/adrs/ADR-P2-020.md) for details.

## How to review this Repository
The repo is structured for progressive discovery. Start with the README and demo, then go deeper based on what you want to explore.

1. **README** (this page): overview of architecture, constraints, validation results
2. **[Live Demo](https://34.27.245.64.sslip.io/)**: the deployed system running on a free-tier VM
3. **[Tracer Walkthrough Notebooks](/notebooks/01_demos/01_tracer/README.md)**: four notebooks that start at the runtime backend (anchored to the demo you just played). From there they step back to the beginning of the offline system and follows the generation and processing of a single synthetic question batch forward to the runtime handoff:
    - Runtime → Generation → Validation → Context Enrichment with Runtime handoff
4. **[Design Doc & ADRs](docs/00_DESIGN_DOC_AND_ARCHITECTURE.md)**: full 
   architecture specification, trade-off rationale, and decision records
5. **[Research Notebooks](/notebooks/02_research/)**: EDA, semantic deduplication, 
   SBERT analysis, prompt engineering experiments *(DS / NLP path)*
6. **[Pipeline Scripts](/scripts/pipelines/generate_questions/) + [Game Source](/src)** 
   — Prefect orchestration structure (*work in progress*), MVC (Model-View-Controller) architecture, evaluator router *(ML / AI systems path)*.

## A note on the design approach

My background is in chemical process engineering, where systems are designed against physical constraints, validated before scaling, and measured against outcomes. This project applies that mindset to ML systems. 

The project evolved through a combination of upfront design and iterative discovery, addressing limitations as they became visible. Brittle exact matching led to semantic answer evaluation. A small, inconsistent dataset led to automated generation and validation. Each addition addressed a specific constraint or failure mode that emerged during development.

The design responses were integrated back into the overall system design. This kept the system grounded in current constraints while leaving room for future extension.

The project breadth is wide and cross-disciplinary by design. It is structured as a learning ecosystem spanning data science, system design, and MLOps. The goal is to understand how conceptual chemical engineering design translates to AI engineering. Mapping the landscape, finding where my design experience transfers and where it doesn't, is as much the point as the system itself.

## Project Status
This project follows an architecture-first, iterative development lifecycle outlined in the [Design Doc](/docs/00_DESIGN_DOC_AND_ARCHITECTURE.md).

✅ **Phase 1: Data science discovery and game foundation** [COMPLETE]
- Discover and explore problem space and surface failure modes.
- Activities: EDA, baseline dataset construction, schema definition, MVC game architecture, and MVP deployment
with exact-match evaluation.

<details>
<summary><i>Click to expand Phase 1 data science & MVP metrics</i></summary>

### Phase 1 focused on discovery & prototyping
The raw dataset was manually curated and standardized to build the Baseline (v0) dataset. This manual process exposed the scalability bottlenecks that directly informed the [Content Factory architecture](docs/00_DESIGN_DOC_AND_ARCHITECTURE.md#p2-content-factory-architecture-in-depth) for Phase 2.

|Metric|Value|Description|
|-|-|-|
|Data Optimization|1279 → 902|Aggressive pruning (Q-Q cosine similarity) + Strategic Enrichment (100+ new explanatory items, 240+ rehabilitated)|
|Topic Diversity|86% unique|Answer-Answer (A-A) analysis confirmed high semantic variety, limiting repetition to core entities.|
|Taxonomy (interrogative identifier)|100%|Achieved complete categorization coverage using a custom tokenizer & lemmatization script. This is important because it is used to classify questions into the main types (Explanatory, Factual-Recall, Multiple-Choice, Yes/No)|
|Class Balance|Baseline_v0 dataset|78% Factual Recall, 11% Explanatory, 10% MCQ, 1% Yes/No.|
|Schema Validation|	Pass	|Ingestion script with standardized schema checks, automated deduplications minimized error when appending to the main dataset|
|Game Core|	MVP	|Python MVC (Model-View-Controller) Architecture w/ pytest coverage|

#### Key Analytical Insights
* **Linguistic fingerprint:** Answer length can be used to distinguish between Explanatory (EX) from other short-answer types (FR, MCQ, YN). The [boxplot analysis (item 3 below)](#phase-1-visual-artifacts) shows the interquartile range for EX answers (8-22 words) does not overlap with FR, MCQ, or YN.
    * *Architectural Implication:* Phase 2 monitors answer-shape patterns as the dataset grows to preserve consistency across question types. See [ADR-P2-014](docs/adrs/ADR-P2-014.md) for the full rationale and monitoring approach.
- **Vector drift**: The TF-IDF vectorizer struggled with the vocabulary shift introduced by new *explanatory* (EX) questions, directly motivating the switch to Sentence-BERT (SBERT) for Phase 2 deduplication.
- **Question-type imbalance**: The baseline dataset was heavily skewed toward Factual Recall (78%). This imbalance drove the requirement for the Phase 2 *Content Factory* to synthetically generate complex "Why/How" questions. These type of questions are key differentiators for the game experience. It should also be able to generate the other question types to keep dataset in balance.

#### Phase-1 Visual Artifacts

1. Interrogative keyword distribution (100% coverage) 
    <details>
    <summary><i>🔎 View the keyword distribution plot</i></summary>

    [![Interrogative keyword distribution](assets/docs/phase1/p1_keyword_graph.png)](assets/docs/phase1/p1_keyword_graph.png)
    *(Click image to open full resolution)*
    </details>
    <br>

2. Baseline v.0 dataset status map 
    <details>
    <summary><i>🔎 View Baseline v0 Status Map</i></summary>

    [![Baseline Dashboard](assets/docs/phase1/p1_baseline_v0_statusmap.png)](assets/docs/phase1/p1_baseline_v0_statusmap.png)
    *(Click image to open full resolution)*
    </details>
    <br>

3. *Box plot of Answer Length vs. Question type (Baseline v.0 dataset)*
    <details>
    <summary><i>🔎 View the keyword distribution plot</i></summary>

    [![Boxplot: Answer len vs. question type](assets/docs/phase1/p1_baseline_v0_boxplot_ans_len.png)](assets/docs/phase1/p1_baseline_v0_boxplot_ans_len.png)
    *(Click image to open full resolution)*
    </details>

</details>

<br>

🚧 **Phase 2: End-to-end core system validation** [TRACER COMPLETE]
- **On-going**: metrics gathering;  
- **Next:** stabilizing based on tracer findings, layering automation on confirmed logic, and updating the design to reflect the tracer lessons.
<details><summary><i>Expand to view status of milestones</i></summary>

|Milestone|Status|
|-|-|
|Prompt engineering and generation quality validation|✅ Complete|
|Validated Tracer dataset (104 Legacy + 35 Synthetic across FR, EX, MCQ)|✅ Complete|
|End-to-end tracer logic validation (notebooks: generation → validation → enrichment → runtime)|✅ Complete|
|Runtime container deployment (GCP VM, Docker, Tailscale)|✅ Complete|
|Runtime performance metrics collection|🚧 In progress|
|Prefect pipeline automation — generation|🚧 In progress|
|Prefect pipeline automation — validation|📋 Planned|
|FastAPI service layer|📋 Planned|

Refer to [engineering backlog](/docs/03_engineering_backlog.md) for further details. 
</details>


## Tech Stack

|Layer|Technologies|
|-|-|
|Language & Runtime|Python 3.12, Parquet|
|AI & Semantics| Google Gemini 2.5 Flash, Sentence-BERT (SBERT), NLTK|
|Validation|Pydantic V2|
|MLOps & Orchestration| Prefect, DVC, Docker|
|Infrastructure|Google Cloud VM, Google Cloud Storage, Tailscale, GoTTY|
|Testing|pytest|

See [requirements.txt](requirements.txt) for packages required to run the game, and [requirements-dev.txt](requirements-dev.txt) for the complete list of tools used in the game as well as notebooks, data processing, and advanced NLP work.

## Data Sources & License

See [Data Sources](DATA_SOURCES.md) for all dataset provenance and usage documentation. <br>
This project's code is licensed under the [MIT License](LICENSE-MIT).


<details>
<summary>Data usage note</summary>

- *Raw Inputs*: The original raw trivia data used for Phase 1 baseline testing is documented in [Data_Sources.md](DATA_SOURCES.md) and is not redistributed in this repository.
- *Gold Dataset*: The runtime database is a hybrid asset. It consists of the original source data (cleaned, normalized, and validated) augmented with synthetic content and metadata generated via the Content Factory. To respect original copyrights, the full gold dataset is not included in this repository.

</details>

<br>

---
*Disclaimer: this project is an unofficial educational fan tribute to the Harry Potter series. Not affiliated with or endorsed by J.K. Rowling, Warner Bros., or any related parties.*
