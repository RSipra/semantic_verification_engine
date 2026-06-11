<!-- 
==================== POLISH PASS — TODO (after correctness) ====================
Context: correctness pass makes the doc internally consistent/accurate. This polish 
pass makes it LAND for the reader who skims (which is almost everyone — hardly anyone 
reads it all carefully). Do this AFTER correctness, on a stable base.

--- 1. SYSTEMS-THINKING SECTION → Option B (summary + link out) ---
WHY: It's an experimental tangent — different register (methodology exploration) from 
the rest of the doc (decisions/architecture). Feels out of place. BUT its outputs are 
real (hallucination ~1% target, ~15-q sessions, feedback-weak-at-demo-scale, acceptance 
sampling) and fed actual decisions (ADR-P2-015, session sizing).
DO: Reduce main-doc section to a short "constraints derived from systems analysis" 
summary + the concrete takeaways, link full walkthrough to /docs/02_system_thinking_casestudy.md.
REMEMBER: repoint references that cite it (ADR-P2-015 SQC, session sizing) to new location.

--- 2. README FRONT DOOR / SKIM-SURVIVAL ---
WHY: Most readers spend 2-5 min, never reach the deep layers. The messages that PERSUADE 
must be above-the-fold on the README first screen, standalone. The depth backs it up when 
checked; the surface does the actual convincing.
DO: Make sure the README's first screen carries, on its own:
  - "validation surface, not a trivia product" (stops the HP-first-impression misread)
  - "designed to scale" (see #3)
  - "deliberate depth / learning sandbox" (frames the over-engineering correctly)
REMEMBER: the primary diagram must carry the offline/online split at a glance — skimmers 
read pictures before prose.

--- 3. SCALABILITY THROUGH-LINE (place early) ---
WHY: Scaling-by-design IS in the doc but SCATTERED (offline/online split, stable interfaces, 
staggered upgrade, Phase 3 options) — each framed by its local concern, never tied to one 
thread. A skimmer misses it; a careful reader has to assemble it themselves.
DO: Add ONE framing statement early (Design Philosophy or Basis for Design): scalability is 
a primary driver; offline/lean-runtime split + stable interfaces mean the system scales by 
changing HOW components are hosted, not WHAT the runtime does. Let later sections reference back.
REMEMBER: the interface-stability insight (modules→services, SBERT→microservice, runtime 
stays lean regardless of hosting) is the STRONGEST scaling argument but currently only 
appears late in Phase 3. Promote it early as a core principle.

--- 4. FORWARD-REFERENCES TO TELEMETRY SECTION ---
WHY: Numbers (69% local resolution, latency targets, cost deviation) appear in multiple 
sections (evaluator, BoD) but the consolidated source-of-truth is the new Tracer Feedback 
& Telemetry section. Right now they'd float unsourced.
DO: Point inline numbers to the telemetry section, e.g. "~69% resolve locally (see Tracer 
Feedback & Telemetry)". One authoritative home; sections reference it.
REMEMBER: only do this AFTER the telemetry section is filled with real numbers (post 
telemetry-gathering) — no point linking to an empty placeholder.

--- 5. LAYERING / ON-RAMP (if time) ---
WHY: Doc is dense and uniformly so — no fast path. A skimmer hits invariant tables and 
Pydantic chains with no "2-minute version" first. Density is fine for the deep reader IF 
there's an on-ramp for everyone else.
DO: Consider a short exec summary at the very top (thesis, 3 subsystems, key decisions, 
status) so a reader gets the shape in 2 min, then chooses depth. Mark deep mechanics as 
reference/collapsible.
REMEMBER: don't CUT depth — it's what makes the surface true and rewards the checker. Just 
add the fast path on top. This is lowest priority — only if the others are done.

==================== END POLISH TODO ====================
-->

# Design Doc & Architectural Decision Records 

**Project: Semantic Verification Engine**<br>
**Author: Reema Sipra**<br>
**Status: Living Document** (design frozen per Phase)<br>

---

This document outlines the architectural evolution of the Semantic Verification Engine (SVE). It provides:
1. [**Project Plan**](#1-project-plan): defines [goals](#11-project-goals), [design approach](#12-design-approach), [problem space](#13-problem-space), [design philosophy](#14-design-philosophy-applied-systems-thinking), and [basis for design](#15-basis-for-design).
2. **Architectural Schemes & ADRS** Detailed diagrams and decision records (ADRs) for each engineering phase.
    - **[Phase 1: The MVP (Legacy)](#phase-1-discovery--foundation)**
     Rules-based logic, MVC patterned game, standalone container.
    - **[Phase 2: System + Semantic Intelligence](#phase-2-end-to-end-system--semantic-intelligence)**
     Automated question generation, contextual feature enrichment, and semantic answer checking using Sentence-BERT.
    - **[Phase 3: Optional Runtime Enhancement](#phase-3-optional-runtime-enhancements)**
    Improve perceived game intelligence through optional, controlled use of an SLM or LLM.
3. [**System thinking analysis**](#3-system-thinking-analysis): A high-level, conceptual exercise to holistically and dynamically assess the architecture and its design implications as part of the project case study.
4. [**Architectural mapping**](#4-technical-architecture--pattern-mapping) of the project design to industrial patterns to validate and inform decisions.
> **Note on Execution:** This document groups system evolution into logical engineering *Phases*, however the actual delivery would be executed as agile sprints to prioritize the product releases. For the current development roadmap refer to the **[Execution Plan](../docs/01_EXECUTION_PLAN.md)**.

---
<br>

# 1: Project Plan

>Quick links: &nbsp;&nbsp;&nbsp;[[Project Goals](#11-project-goals)]&nbsp;&nbsp;&nbsp;[[Design Approach]](#12-design-approach)&nbsp;&nbsp;&nbsp;[[Problem Space](#13-problem-space)]&nbsp;&nbsp;&nbsp;[[Design Philosophy](#14-design-philosophy-applied-systems-thinking)]&nbsp;&nbsp;&nbsp;[[Basis for Design](#15-basis-for-design)]

## 1.1: Project goals

1. **Product**: Build an intelligent, domain-centric trivia game demo that prioritizes correctness, low latency, and a smooth game experience. The focus is on a constrained knowledge base and efficient delivery, at free or very low cost.
2. **Personal development**: Deepen hands-on expertise in NLP, software architecture, and MLOps by designing and implementing an end-to-end AI system using professional deployment and operational standards.
3. **Cross-domain exploration:**: Apply chemical engineering practices (Front-End Loading, systems thinking) to software and AI design, exploring how rigorous upfront planning could complement fast, iterative execution.

    Software and ML move fast, with many ways to solve the same problem. The ADRs make design thinking explicit, clarify trade-offs, and document patterns, both to guide current implementation and serve as a reference for future projects.

    The architecture guides implementation, ensuring design decisions are validated against actual performance. 

## 1.2: Design Approach
This project applies rigorous system design to a constrained domain, with the architecture emerging iteratively as discovery surfaced new constraints. It serves two parallel goals: validating the idea of speed through rigour and accelerating my own learning through practice. As a result the project combines several learning objectives into a single end-to-end system to see how they interact:

1. **Data Science (the core)**: exploratory data analysis (EDA), contextual feature engineering, semantic similarity evaluation, and select fit-for-purpose NLP techniques.
2. **System Design (the blueprint)**: Translating the data science insights into architectural constraints and viable trade-offs.
3. **MLOps & Agile (the execution)**: Evolving those constraints into a resilient system iteratively.

The goal is a system design with clearly defined boundaries, roles, and constraints and aligned with [established architectural patterns](#4-technical-architecture--pattern-mapping). This document focuses on architectural clarity rather than production deployment.

💡 **The Interdisciplinary Lens**.
This project explores questions that emerged during development:
- **Front-End Loading (FEL) & Agile**: FEL resembles the *Design Doc / RFC* phase (definition before execution to mitigate risks and costs).  So *where  does early design prevent rework and where does it introduce friction?*
- **Process design & System thinking** Both aim to define constraints early, reason about flows, and reduce downstream issues. *How do these approaches overlap or differ?*

**Context**:  Coming from a chemical engineering background, I have seen the value of rigorous upfront design in high-risk systems, but I am also aware of its limitations (rigidity, slow feedback). This project deliberately plays with that tension and explores how disciplined systems thinking can support fast, iterative delivery.

## 1.3: Problem space
Based on the learnings from the [discovery stage](#phase-1-discovery--foundation) (Phase 1), the key challenges are:

1. **Data scarcity**: The existing question pool is small with limited quality. Manual curation is time consuming, error prone, and inefficient. 
2. **Data saturation**: Limited source material (Harry Potter books) constrains variety.
3. **Closed-domain application**: Focused on a trivia / Q&A session orchestration, not open-ended chat.
4. **Sustainable economics**: Demo must be low-cost and maintainable. Viable paths to scale should be integrated to avoid runaway costs and keep operational expenses manageable.
5. **Correctness and accuracy** of the questions and answers are critical for player trust and game credibility.
6. **Game UX**: Smooth front-end experience for player engagement. 
7. **Replayability**: Adequate variety across sessions to maintain interest.  For long-term engagement, the experience should remain fresh even when the factual content (the dataset) remains static.

## 1.4: Design philosophy (applied systems thinking)

The design of the project is grounded from the start by looking at the project lifecycle as an interconnected whole. The core approach has four main aspects:

1. **Agile Front-End Loading (FEL)**: Combine upfront design with iterative sprints to balance planning and execution..
2. **Upstream optimization ("shifting left")**: Solve problems early to reduce downstream complexity. By solving problems earlier, we can trade higher initial effort for permanent gains in runtime speed, cost, efficiency, and reliability once the product is live.
3. **Systematic evolution**: As the project progresses, requirements will inevitably change. Components evolve systematically, with reusable, extensible, and feedback-driven design.
4. **Swiss cheese approach**: layered defensive strategy (prevention, detection, correction) for data quality assurance.

## 1.5: Basis for Design
Design constraints are iteratively refined using telemetry from the system tracer, which provides empirical feedback on runtime performance, routing behavior, and LLM dependency patterns.

Constraints and target boundaries:

||**Constraint**|**Requirement**|**Target**|**Safety margin /**<br>**Contingency**|
|-|-|-|-|-|
|1|**Economics**|**minimum-cost operation**.The project demo must not incur any costs during development and be able to operate indefinitely without any operational costs|$0 -$5 fixed monthly cost|Apply hard budget alerts with a circuit-breaker set at $20.00/month|
|2|**Performance**|**Low-latency**. Gameplay interactions need to feel instantaneous to maintain user immersion|local inference < 500ms latency (p95)<br> llm path < 1~2s (p95)|Apply UX fallbacks to remain within acceptable UX limit (< 5s). Optimize resolution with local inference where possible. |
|3|**Quality**|**Domain authenticity**. Content must be tonally consistent and canonically accurate to satisfy fan base (tweens to adults)|100% Verifiable (books 1-7, movies, Rowling's supportive works)|Swiss cheese logic (multi-layered validation)|
|4|**Capacity**|**Demo scale**. System needs to be sized to handle expected concurrent users within cost (free) limits.|5 - 10 concurrent users|Graceful Degradation. Implement load shedding or request queuing rather than crashing or incurring unplanned costs.|
|5|**Scalability**|**Future-Proof economics**. Design should demonstrate viable path to scale where growth doesn't erode margins (capex vs. opex)|Constant or decreasing unit cost|Prototype & projection. Use "tracer bullet" experiments to empirically validate assumptions before committing to the architectural pattern|

### Objective
Build a smart, domain-centric trivia game demo that prioritizes correctness, low latency, and a smooth game experience with minimal cost.

---

# 2: Architectural Schemes & ADRs
The project development is broken into parts: 

Phase|Link|Function| Risk Mitigated|ADR Summary|
|-|-|-|-|-|
|1|[Discovery & Foundation](#phase-1-discovery--foundation)|**Logic core & Baseline.** Establishes the MVP game state logic and a manually curated dataset, serving as the functional blueprint for subsequent automation. Kiosk-style, cloud-based containerized demo| **Viability & Quality Risk**. Validates game mechanics and identifies critical data gaps (skew, bias, completeness) in the manual baseline.| [P1 Key Decisions](#p1-key-decisions)|
|2|[End-to-End System + Semantic intelligence](#phase-2-end-to-end-system--semantic-intelligence)|**Design Backbone with Semantic Upgrade.** Critical path for synthetic generation, contextual enrichment, and semantic answer checking, with runtime upgrades (logging, automated GitHub interactions).|**Quality, logic, and economic risk.** Mitigates dataset limitations identified in Phase 1, resolves exact-match brittleness, and tests cost viability under free-tier constraints.| [P2 Key Decisions](#p2-key-decisions-adrs)|
|3|[Optional Runtime Enhancements](#phase-3-optional-runtime-enhancements)|**Constrained use of an SLM/LLM to enhance interaction**. Open design space, decision pending Phase 2 learnings|**Premature-commitment risk**. Deferring the hosting/intelligence decision until feedback (scale, user interest, data sensitivity) justifies a specific path|

<br>

📝 **Note on execution strategy**: <br>
The architecture is presented linearly. However, early tracer-bullet experiments are used to validate runtime cost, latency, and viability upfront. For execution details, see the [execution plan](01_execution_plan).

<br>

---
# PHASE 1: Discovery & Foundation 
**Objective**: Develop core components of game, identify pain points.

## P1 Overall Development Scheme
![Phase 1 development scheme](../assets/docs/phase2/phase1_dev_main.jpg)
**Figure 1.** High-level development scheme showing the components involved in developing the baseline dataset and integrating it with the game engine.

The EDA module (`cleaning & EDA notebook`) is responsible for validating the raw dataset and profiling its structure, quality, and source-content coverage. Insights produced at this stage inform downstream processing.

Data then flows into the processing module (`processing & feature engineering notebook`). This component provides the core transformation layer of the scheme. Its responsibilities include:
1.  Remove incomplete, incorrect, and out-of-scope questions by manual review and executing automated semantic-deduplication logic.
2. Establishing and enforcing the standardized schema required for the baseline dataset.
3. Integrating curated, high-quality replacement questions through an automated ingestion script, with changes to the dataset monitored using a status dashboard for monitoring

The output of this processing layer is the `Baseline Trivia Dataset v0`, exported as a local CSV artifact. This serves as the data layer for the MVC-based CLI game application, which consumes the dataset for question delivery and gameplay logic.

## P1 Key Decisions

|**ADR ID**|**Title**|**Status**|**Summary**|
|-|-|-|-|
|[ADR-P1-001](adrs/ADR-P1-001.md)| Game design (SOC & MVC pattern)|✅ Accepted<br>(retroactive)|Separates Logic/Data/View to enable future web porting|
|[ADR-P1-002](adrs/ADR-P1-002.md)|Dataset storage (CSV vs Parquet)|✅ Accepted<br>(retroactive)|Maintain data types when porting between notebooks (and pipelines in future)|
|[ADR-P1-003](adrs/ADR-P1-003.md)| Data ingestion control flow (Status/Payload Pattern)|✅ Accepted<br>(retroactive)|Allows the user to handle partial success states (e.g. semantic duplicates) when ingesting new questions|
|[ADR-P1-004](adrs/ADR-P1-004.md) | Stateful VM deployment strategy | ✅ Accepted | Deploy the trivia game as a  web-terminal on a VM for a rapid launch with minimal refactoring.|

*Refer to the linked Architectural Decision Records (ADRs) in the table for full details*.

## P1 Game Internal Architecture (CLI-MVP)

The trivia game is built in Python using a Model-View-Controller (MVC) setup. The pattern allows for modularity, where the `View` interface can be decoupled from the core logic for an eventual transition to a web UI. The `rich` library was used to elevate the terminal experience as clean and fun. 

**Core Objectives of the MVP**
- *Validate game logic*: Ensure the end-to-end flow, from loading questions to scoring and completion, is stable and error-free.
- *Identify answer-matching limitations*: Use this phase to document where exact text-matching fails and confirm whether semantic-answer checking is justified.

<br>

[<img src="../assets/docs/phase2/phase1_dev_mvp.jpg" alt="MVP_MVC_architecture" height="550"/>](../assets/docs/phase2/phase1_dev_mvp.jpg)
<br>
**Figure 2.** CLI-MVP Game architecture with Class interactions. *Click on figure for an expanded view.*

## P1 Runtime Environment (CLI-MVP)

**Design**: Embedded read-only architecture <br>

The dataset is baked directly into the container as a static file. This keeps the implementation simple and robust and meets the design constraints:
- **Zero gametime latency**: The game samples ~10 ~20 questions immediately from local memory at startup.
- **Operational simplicity**: The container is self-contained. Since the dataset is small (~1K records) and the source domain is finite, updates are infrequent. This eliminates the need for any complex database connections or constant read operations.
- **Separation of concerns**: Heavy data operations are handled offline. The runtime environment is strictly read-only, optimized for speed and portability.

<br>

[<img src="../assets/docs/phase2/phase1_dev_runtime.jpg" alt="MVP runtime architecture" height="500"/>](../assets/docs/phase2/phase1_dev_runtime.jpg) 
<br>
**Figure 3.** Phase 1 CLI-MVP demo deployed as a container on a Google Cloud Platform (GCP) Virtual Machine. *Click on figure for an expanded view.*

### Implementation and deployment strategy

The goal for Phase 1 is a *frictionless player experience*. This requires a secure, continuously available demo deployed with minimum refactoring and minimum cost. This required iterating two aspects:

#### 1. User Experience (UX)
The original CLI-MVP (v0) came across as a *wall of text* which hindered immersion in the game. So minimum refactoring (v.0.1) was done to the View and Controller classes to provide focused, incremental views (e.g. displaying one question at a time) to better suit a web-terminal interface.

#### 2. Runtime system design and security

- *Immediate deployment*:  Since the CLI-MVP game is working, a cloud-hosted Virtual Machine (VM) wrapped as a web terminal (using Gotty) would allow the game to run within the browser without refactoring (*figure 3*).
- *User trust*: the http "not secure" warnings before the game start would make Players hesitate to try the game. To mititgate, a short-term $4/month fee was acceptable for a static IP address for the VM or Let’s Encrypt (via Caddy) could verify our domain and issue certificates and enable https. Since phase 1 demo is short-term until the phase 2 demo comes online, the cost is acceptable.
- *Availability*: Using the `e2-micro` instance on Google cloud made the game persistently available within the free-tier. Note: running is cheaper than turning it off, since Google charges for unused static IPs.
- *Layered defenses*: There are three layers to handle different risks of deploying to the internet:
    1. GCP Firewall: The first line of defense to filter out bots and noise.
    2. UFW (VM Firewall) & Caddy: Encrypted traffic is managed by Caddy, and UFW limits VM access to only essential services (HTTPS, SSH).
    3. Docker Sandboxing: The containerized game engine is isolated from the host OS, ensuring the application has no access to cloud system configuration. This also streamlines with the phase 2 serverless design.
- *Admin Access*: Management is handled via a secure SSH connection through a Tailscale tunnel, featuring real-time, bi-directional workspace sync for rapid updates.
- *AI orchestration*: Gemini was used as a technical collaborator to iteratively develop, refine, and troubleshoot syntax-heavy infrastructure components, including Dockerfiles, Caddyfiles, and UFW configurations.
- Refer to [ADR-P1-004](adrs/ADR-P1-004.md) and [P1 runtime architecture doc](archive/phase1_legacy/02-P1_runtime_architecture.md) for further details.

## P1 Design Limitations

1. **Manual dataset modification**: Dataset quality relies on manual, iterative review and cleaning. This process is slow, inconsistent, and prone to errors.
2. **Slow question generation**: Question creation is time-consuming and does not scale efficiently.
3. **Insufficient dataset quality and coverage**: The cleaned baseline dataset is still limited in size and depth. It is not sufficient for SBERT training, lacks strong focus on core lore and books, shows imbalance in question types, and produces mostly straightforward questions. This leaves significant room to improve the experience for knowledgeable fans.
4. **Rigid answer checking**: Answer validation relies on direct string matching making it fragile and leading to a poor user experience.
5. **Rule-based feedback only**: Feedback is deterministic and rule-based which can sometimes fail to reflect in-game context or partial correctness.
6. **User Experience**: The CLI MVP focuses on validating gameplay flow and answer evaluation but Players may not find it engaging.
7. **Limited runtime scalability**: this is constrained by the lightweight VM resources. It can accommodate light multi-user access but it hasn't been tested for sustained concurrent use.

<br>

# PHASE 2: End-to-End System + Semantic Intelligence 

**Objective**: Critical path development, horizontal slicing. Automate content generation and deploy a cloud-native MVP.

## P2 Overall development

This marks a major shift in the project. Phase 2 intentionally concentrates architectural complexity offline so that runtime and gameplay remain simple, fast, and deterministic. It moves from data science experimentation to MLOps infrastructure development and lays the architectural groundwork.

The key value-add here is the introduction of *semantic intelligence* at the interaction level. Players are no longer required to match exact wording when answering questions; the game can recognize differently phrased but equivalent answers, making interaction feel more natural and less rigid.

The figure below shows the overall architecture. The dark purple components (baseline trivia dataset v0 and the game application code) are inherited from phase 1. 

![Phase 2 development scheme](../assets/docs/phase2/phase2_dev_main.jpg)
**Figure 4.** High-level phase 2 system target architecture.

The system is split into three main regions. The first is the *Content factory* is responsible for the data generation and maintenance following a *Medallion pattern*, creates a handoff gold-level dataset. Refer to the [Content Factory in-depth](#p2-content-factory-architecture-in-depth)  section for further details  

The dataset then passes to the second **Context Refinery** subsystem. Here the data is processed for contextual enrichment (e.g NER tags, difficulty labels). The feature logic is developed and validated interactively using notebooks. The new features are added to the `Production` dataset offline keeping the runtime interface stable. 

#### Context enrichment layer

The Context Refinery is a decoupled offline enrichment layer. Feature engineering happens here, separated from the Content Factory and the runtime. This approach aligns with the offline portion of the Feature Store pattern (see [section 4](#4-technical-architecture--pattern-mapping)), though it deliberately stops short of a full feature store; no serving layer, no online parity.

<details>
<summary><i>Expand for design note: how Context Refinery was refined using the Feature Store pattern</i></summary>

### How the Feature Store lens refined the Context Refinery

The Context Refinery was already designed as a decoupled system for adding *contextual information* to questions. Its original role was narrow by intent, to enrich questions with additional context without affecting the runtime path. When this design was later compared against Feature Store pattern it became clear that the Context Refinery was already doing part of the job but could reasonably own all the feature engineering.

This comparison led to a few concrete refinements:
- **Feature engineering is fully centralized in the Context Refinery**: Descriptive features were moved out of the `qa_validation` pipeline in the Content Factory.
- **Semantic feature usage is simplified and unified**: SBERT usage was centralized. Instead of re-running the model in multiple places, a shared embedding index derived from the Gold dataset is reused for semantic checks and deduplication.
- **Notebooks are treated explicitly as prototypes**: Feature notebooks are written with the assumption that they are temporary; a place to explore and validate logic before it is hardened into an automated pipeline later.

This shift did not change the system’s behavior, but it clarified responsibilities and reduced duplication. It also directly informed the next Phase design for the Context Refinery 

**Future iteration (conceptual): more automated feature workflow**

A natural next step is to automate parts of this workflow so new features can be added without relying on notebooks. In its simplest form, this would not require a full Feature Store service. A lightweight interaction layer (e.g. script with structured inputs) would be enough to trigger feature generation using the same validated logic already in place. This would make feature addition faster and more consistent, while keeping the system lean and aligned with the existing design.

</details>

#### Multiple use of SBERT across the system

The SBERT model's primary purpose is semantic answer checking at runtime but it also enables offline capabilities. Using a *single-producer, multi-consumer pattern* → the model is generated once and consumed by multiple independent components: the Content Factory (for validation), the runtime (for answer checking), and the production dataset (as reference embeddings).

#### Player Answer Evaluation
The game uses tiered, hybrid answer-checking to balance speed and determinism with correctness. Evaluation splits at two levels.

*Main router*: diverts by text and non-text answers (date, year, numeric).
A non-text answer subrouter delivers the payload to structured evaluators. A text answer subrouter dispatches to semantic evaluators based on question type.

*Structured evalautors*: non-text player answers go directly to deterministic, rule-based evaluators against split on answer type ; no semantic or model inference involved.

*Semantic evaluators*: the text answer subrouter than dispatches to an evaluator based on question type (MCQ, EX, FR). Tiers are ordered to resolve as early as possible:
1. Exact match (local inference)
2. Fuzzy match (local inference)
3. Semantic similarity (Sentence-BERT; local inference)
4. NLI verification (local inference, logic integrated; activates with planned claim-decomposition)
5. LLM escalation (bounded last-resort judge)

<details>
<summary><i>Evaluator decision logic — FR and EX flow diagrams</i></summary>
<br>

**FR (Factual Recall) evaluator**: Tiered with early exits at each stage. The verbosity bypass routes 
over-long answers directly to LLM.
![FR evaluator logic](/assets/docs/phase2/fr_evaluator_logic.jpg)

<br>

**EX (Explanatory) evaluator**: SBERT acts as a filter, not a resolver. The wide ambiguous band (between semantic threshold and ambiguous cutoff) are all passed to LLM for final resolution in the tracer. NLI is implemented but proved ineffective without decomposing the answers into atomic claims. Disabled for Tracer till claims are implemented.
![EX evaluator logic](/assets/docs/phase2/ex_evaluator_logic_v0-1.jpg)

</details>

<br>

MCQ types are the simplest and can be resolved with the first three tiers. FR (short 1-3 words) are also largely handled locally . Long answers (verbose player answers or outlier dataset answer lengths) bypass SBERT and are escalated directly to LLM, since sentence-level similarity is unreliable here. The explanatory (EX) answers that are long, multi-component, and vary largely require all evaluation tiers.

The tiered structure emerged through iterative evaluator development during the tracer build. SBERT alone capped at ~60% accuracy on long Explanatory answers, which carry multiple implicit claims that sentence-level similarity cannot reliably verify. Adding a bounded LLM judge as the final tier raised evaluator accuracy to 85–93%. The LLM is the last-resort tier. Tracer telemetry shows ~69% of questions resolve locally without an LLM call.

### Phase 2 Architectural Invariants
This section captures the core assumptions the system relies on to remain correct and predictable. These invariants define ownership, data flow direction, and consistency rules that shape the SVE system behavior. Making them explicit helps guide future changes and prevents accidental violations as the system evolves

| Invariant | Description | Enforced by |
|---------|------------|------------|
| **Single semantic source of truth** | Embeddings and semantic comparison rules have exactly one authoritative origin.|qa_validation pipeline ([ADR-P2-013](#p2-key-decisions-adrs)). |
| **Single active SBERT model** | Exactly one SBERT model version is active across all offline pipelines and runtime at any time. | NLP Lab + pipeline validation ([ADR-P2-013](#p2-key-decisions-adrs)).|
|**Embedding-Schema coherence**|No record advances a tier without a valid embedding from the active model.| Pydantic schema gate|
| **Append-only system of record** | The audit ledger is never mutated in place; corrections are new entries.|DVC + publishing pipeline|
| **Stateless runtime** | The runtime does not generate or mutate data. It only consumes production-ready artifacts. | Runtime architecture |
| **Offline-first intelligence** | Expensive or high-volume intelligence is performed offline. Runtime logic is optimized for latency and responsiveness. | Phase 2 design |
| **Unidirectional flow** | Data flows unidirectionally from content factory to context refinery. Production datasets are regenerated artifacts and are not used as inputs to Content Factory pipelines. | Publishing pipeline |

**Design note**: Evaluating DVC surfaced an open boundary decision around how much generation metadata to retain for traceability versus shed for a lean runtime dataset. This boundary will be validated after observing real generation → validation → enrichment pipeline runs.

### P2 Data lifecycle

|**Data Tier**|**State**|**Purpose**|**Key data added**|
|-|-|-|-|
|*Bronze*|*Raw*|Ingestion & Schema Check|`question_source`, `data_tier`|
|*Silver* | system of record (invariant + traceable ledger) | truth layer for all validation + audit + lineage | cleaned strings, validated MCQ logic, deduplication flags, grounding checks, **`master_id`**, SBERT embeddings, model versions, full trace metadata |
| *Gold* | *derived runtime contract (pruned projection of Silver)*| lean runtime mirror for game + Context Refinery handoff | minimal game-ready fields (metadata stripped) |
|*Production_Green*|*full, feature-rich*|Full-schema production dataset including dev and experimentation feature|NER tags, Contextual Features, Descriptive Features|
|*Production_Blue*|*lean, feature-rich*|Stable, lean runtime ready dataset with only columns necessary for game handoff|Optimized subset of NER/Contextual features required for runtime.|

**Architecture Notes**: 
The data-tiers are managed and gatekept using Pydantic v2 models with sequential inheritance from 
BaseModel -> [Bronze_Legacy | Bronze_Synthetic] (parallel ingestion) -> Silver (system of record / invariant ledger) → Gold (derived runtime contract) → Production layers (feature views): {Production_Green | Production_Blue} (branching inheritance).

<details><summary><i>Expand to view further discussion and explanation</i></summary>


**1.The Silver-Gold Separation of Concerns**
To ensure low-latency handoffs to downstream systems while maintaining clear traceability of LLM-generated content, a strict separation of concerns is enforced between the Silver and Gold tiers:
- *Silver (audit ledger)*: An append-only historical log. It retains every LLM evaluation trace, pipeline margin score, and model version. If a generated question exhibits a flaw in production, it will be queried in the Silver ledger to trace the exact prompt, grounding source quote, and validation logic that allowed it to pass.
- *Gold (runtime contract)*: A derived, stripped projection of the Silver system-of-record. It contains only the fields required for runtime execution and downstream contextual enrichment. All heavy pipeline metadata and trace logs are stripped out. It contains only the strictly-typed, normalized data required to serve the game, ensuring the downstream Context Refinery is not bloated by upstream engineering logs.

**2. Production Green (development) & Blue (stable) Separation of concerns**
These datasets handle the handoff between the *Context Refinery* and the *Runtime Game* subsystems.
- *Production_Green* dataset:  This is used for feature discovery and MLOps telemetry. It contains the full suite of features (e.g. token counts, keyword tokens, NLP metadata). This dataset is for experimentation, as well as assessment and fine-tuning of the answer checking evaluators and semantic thresholds, error analysis and debugging.
- *Production_Blue* dataset: lean runtime for optimized performance (mirror of *Green* where unnecessary gametime columns are shed). This allows for stable version for the Docker container with focus on game performance and answer evaluation.
The lifecycle will be managed as follows:
- *Schema decoupling*: Both systems inherit from the Gold dataset, ensuring a singular source of truth for core trivia while allowing the refinery to branch for different use cases (development vs. stable runtime).
- *Promotion workflow*: once a feature is vetted and finalized in the Green and is used in the game logic, it is promoted to the Blue schema.
- *Live, symmetric tensor generation*: Both mirrors utilize static embeddings that are hydrated into live PyTorch tensors during the session warmup ensuring high-speed matrix operations during the answer evaluation.
- *Router with Production DTO options*: enables the game engine to toggle between Blue (stable mode) and Green (development / debug mode) without modifying the evaluation logic.

**3. Object-oriented evaluation contract for the Answer Evaluators**: The pydantic schema is the interface for the runtime Answer Evaluators. So instead of passing dataframe rows parsed as dicts, the game instantiates them into a `Question` object.
- *Allows for dot-notation*: This allows for the data to be accessed via strict predefined attributes based on the SOT Pydantic schema (eliminating KeyErrors or column mixups).
- *Schema driven logic*: The `answer_type` Enum defined in the schema is the first dispatch key in the `runtime_router`, splitting answers into text and non-text paths. Text answers route to the semantic subrouter, which dispatches on question_type (FR, EX, MCQ). Non-text answers route to the structured subrouter, which dispatches on the specific answer_type (date, numeric, year) to the matching deterministic evaluator.

</details>

## P2 Key Decisions (ADRs)

| ID | Title | Status | Summary |
| :--- | :--- | :--- | :--- |
| **I. Strategy (core ADRs)** | | | |
| **[ADR-P2-001](adrs/ADR-P2-001.md)** | **"Shift Left" Enrichment** | ✅ Accepted | Move expensive NLP operations (hints, fun facts) from Runtime to the Pipeline to ensure low-latency gameplay. |
| **[ADR-P2-002](adrs/ADR-P2-002.md)** | **Medallion Data Architecture** | ✅ Accepted (updated) | Organize data into Bronze (raw), Silver (system of record), and Gold (projection) layers to ensure traceability and safe checkpoints. |
| **[ADR-P2-003](adrs/ADR-P2-003.md)** | **Context Refinery Pattern** | ✅ Accepted | Move descriptive feature generation out of the Content Factory. Context Refinery is an offline enrichment layer (aligned with the offline portion of a feature store). |
| **[ADR-P2-004](adrs/ADR-P2-004.md)** | **Generative Model (Gemini)** | ✅ Accepted | Standardize on **Google Gemini** for synthetic data generation due to superior cost-performance ratio and native integration with the GCP stack. |
|[ADR-P2-005](adrs/ADR-P2-005.md)|**Tiered semantic answer-checking strategy**|✅ Accepted<br>(updated)|Use a tiered approach to balance latency and correctness: (1) direct match, (2) fuzzy match, (3) semantic similarity using Sentence-BERT (4) NLI (disabled for tracer) (5) LLM judge fallback|
| **[ADR-P2-013](adrs/ADR-P2-013.md)** | **Centralized Semantic Validation Strategy** | ✅ Accepted (updated) | Establishes the Silver dataset as the single source of truth for semantic embeddings and standardizes semantic validation using a single SBERT model across the system.|
|**[ADR-P2-017](adrs/ADR-P2-017.md)**| Serverless Deployment | ✅ Accepted | Move to a managed container service to enable automatic scaling, reduce operational maintenance, and support a multi-user FastAPI backend.|
<br>

<details>
<summary><strong>👇 Expand to view supporting ADRs (implementation, tooling, experiments, and deferred decisions)</strong></summary>
<br>

| ID | Title | Status | Summary |
| :--- | :--- | :--- | :--- |
| **II. Infrastructure** | | | |
| **[ADR-P2-006](adrs/ADR-P2-006.md)** | **API Framework (FastAPI)** | ✅ Accepted | Select FastAPI over Flask for native Pydantic integration, async performance, and automatic documentation. |
| **[ADR-P2-007](adrs/ADR-P2-007.md)** | **Client Architecture** | ✅ Accepted | Decouple the frontend as a "Remote Terminal" (or Web App) that communicates strictly via HTTP/JSON with the backend. |
| **[ADR-P2-008](adrs/ADR-P2-008.md)** | **Structured Logging (JSON)** | ✅ Accepted | Configure all application and pipeline logs to emit **Structured JSON** rather than raw text, enabling query-based observability in Cloud Logging. |
| **III. Pipeline Engineering** | | | |
| **[ADR-P2-009](adrs/ADR-P2-009.md)** | **Data Versioning (DVC)** | ✅ Accepted | Use **DVC (Data Version Control)** with GCS backend to version large datasets/models, ensuring strict reproducibility between Code and Data. |
| **[ADR-P2-010](adrs/ADR-P2-010.md)** | **Orchestration (Prefect)** | ✅ Accepted | Use Prefect DAGs to manage dependencies, retries, and observability, replacing manual script execution. |
| **[ADR-P2-011](adrs/ADR-P2-011.md)** | **Validation Layer (Pydantic)** | ✅ Accepted | Enforce strict schemas at the "Silver" layer entrance to reject malformed data before expensive enrichment. |
| **[ADR-P2-012](adrs/ADR-P2-012.md)** | **Dataset enrichment pipeline (Notebook → Script transition)** | 🚧 Proposed | **Bootstrap & Shed:** Use a notebook to bootstrap Gold with curated legacy data then shed it after transitioning to automated generation|
|**[ADR-P2-018](adrs/ADR-P2-018.md)**|Stateless Game Architecture for Cloud Deployment|🚧 Proposed|Refactored the MVP from a stateful CLI loop to a stateless request/response architecture, enabling serverless deployment while preserving the `rich` console rendering.|
| **IV. Algorithms & Heuristics** | | | |
| **[ADR-P2-014](adrs/ADR-P2-014.md)** | **Heuristic Stability (LLM Drift)** | ✅ Accepted | Preserves heuristic answer-shape patterns across question types through prompt-led generation and manual, dataset-level monitoring for drift.|
| **[ADR-P2-015](adrs/ADR-P2-015.md)**|**Statistical Quality Control (SQC) for Synthetic Data**|🚧 Proposed|Applies statistical sampling to synthetic data batches as an offline safety net to catch incorrect or hallucinated questions early, using efficient, conditional review to protect user trust at demo scale.|
| **V. Deferred / Superseded** | | | |
| **[ADR-P2-016](adrs/ADR-P2-016.md)** | **Manual Input Swimlane** | ⏳ Deferred | Defers a third manual input swimlane for low-volume, manually curated questions that introduce novelty and gameplay variety in the Content Factory.|
| **[ADR-P2-019](adrs/ADR-P2-019.md)**|**Exclusion of Yes/No (YN) Questions from Gold Dataset**| ✅ Accepted| YN questions provide limited signal for semantic validation in Phase 2 |
<!--Next tag = 20 -->

</details>


---

## 3: System Thinking Analysis

*As a focused case study to explore how systems thinking can augment conceptual design, we explore the Phase 2 design holistically using a systems-thinking lens. The full analysis can be found in [/docs/02_system_thinking_casestudy.md](/docs/02_system_thinking_casestudy.md) and is summarized here.*

Systems thinking is used here as a qualitative, early-stage filter to reason about system behavior (stocks, flows, accumulation, feedback) and to surface key design implications. Its role is to direct focus and prevent premature optimization. A lightweight sensitivity analysis was then used to translate the key behavioral insights into actionable targets and design considerations.

The system was analyzed from two perspectives:
1. **Full system (level 0)**: considers the behaviour of the system against design constraints from generation to runtime handoff, at different **growth scales**. Specifically the shift from the *zero-cost* serverless runtime to paid scale production, and the resulting stress on the runtime environment.
2. **Content Factory (level 1)**: The offline content generation is the primary value driver for this project. While the production can scale with usage, the source content is limited (~7 books), raising questions around dataset saturation and long-term content quality as the system grows.

The system-thinking approach asks you walkthrough your design an understand how it would behave dynamically under different conditions. It helps surface key challenges, identify leverage points, and narrow attention toward dominant behaviors. Sensitivity analysis can then be used to translate these behaviors into actionable targets and design ideas. The main takeaways the analysis revealed are:
1. Hallucination rate target ≈ 1% to maintain user trust and keep downstream correction mechanisms viable.
2. Session size ~ 15 questions to further limit user exposure to residual errors in gameplay.
3. User feedback is a weak correction signal at demo scale and should not be relied upon as the primary quality control mechanism; quality control should be shifted left through active offline QA.
4. Active QA strategies for demo (e.g. sequential acceptance sampling) after each question generation batch. 
5. User feedback signal for correction becomes reliable as a safety-net only at larger scales (~100+ game sessions per day). Provisions for incorporating user feedback should therefore be included in the Phase 2 design, considering a staged strategy that evolves from demo to full-scale operation.
<br>

---

## P2 Content Factory Architecture (in-depth)

**Purpose**: Phase 2 introduces the Content Factory to solve a structural problem uncovered in Phase 1 → a finite, error-prone dataset that must evolve continuously without manual rework or runtime cost.

**The architecture prioritizes offline correctness, traceability, and safe iteration that is a trade-off for pipeline system simplicity.**

![ACES architecture](../assets/docs/phase2/phase2_dev_aces.jpg)
**Figure 5.** Phase 2 Content Factory target architecture (final iteration- #6).<br>

The Silver dataset is initialized by passing the curated legacy questions through the same `qa_validation` pipeline used for synthetic question generation. This ensures that Silver is always materialized through the same single, validation path rather than being treated as a special case at the start.

Once Silver is established, all newly generated questions are validated and deduplicated against the existing Silver dataset. This ordering is intentional; it prevents curated legacy questions from being incorrectly flagged as duplicates of later synthetic content and guarantees that all semantic comparisons are performed using the same logic and thresholds.

Semantic embeddings are generated as part of dataset materialization. All embedding generation occurs within the `qa_validation` pipeline, making the Silver dataset the single semantic source of truth for deduplication and validation across the system.

Gold is then derived from Silver as a schema-gated projection, a lean runtime mirror with audit and trace metadata stripped, handed off to the Context Refinery. Gold carries the embeddings needed for runtime but does not own them; Silver remains the authoritative source.

The system uses an off-the-shelf SBERT model for sentence similarity. Whether to fine-tune remains an open, deferred decision; the ambiguous cases fine-tuning would target (long, multi-claim Explanatory answers) are better handled by the LLM/SLM judge tier, so fine-tuning is currently a lower-value investment. See [ADR-P2-013](../docs/adrs/ADR-P2-013.md) for the full rationale.

### Design evolution
The architecture evolved through iterative validation. Early designs explored several approaches, then implementation helped identify a narrower set of components needed to satisfy the system constraints.

|**Iteration**| **Goal**|**Structural change**|**Limitation exposed**|**Artifact**| 
|-|-|-|-|-|
|**1**|Validate GenAI generation|Linear generation + validation with explicit Bronze → Silver → Gold data flow (Medallion structure)| No mechanism to integrate existing high-quality baseline data|[Diagram: Iteration 1](../assets/docs/phase2/p2_content_factory_iterations/p2_cf_iteration_1.jpg)|
|**2**|Integrate verified baseline data|Two ingestion paths into Bronze layer (synthetic + curated)|Gold dataset could not be safely extended without overwriting or ad-hoc patching|[Diagram: Iteration 2](../assets/docs/phase2/p2_content_factory_iterations/p2_cf_iteration_2.jpg)|
|**3**|Enable safe, repeatable dataset evolution|Replace ad-hoc update scripts with a unified enrichment pipeline supporting multiple execution modes (update, correction, feature addition)|Enrichment pipeline overhead not justified by the expected frequency of change / updates to trivia dataset|[Diagram: Iteration 3](../assets/docs/phase2/p2_content_factory_iterations/p2_cf_iteration_3.jpg)|
|**4**| Improve validation and correction controls|1. SBERT decoupled into index for deduplication<br> 2. manual correction mechanism (Kill list + SOP + modular validation)<br>3. Bootstrap-and-shed enrichment: legacy data updated once via notebook, then shed; shared logic hardened into a enrichment pipeline.|Semantic behavior existed but was not clearly owned or enforced, making consistency across pipelines and runtime ambiguous|[Diagram: Iteration 4](../assets/docs/phase2/p2_content_factory_iterations/p2_cf_iteration_4.jpg)|
|**5**|Semantic ownership & consistency|Semantic validation logic was centralized. Semantic embeddings are treated as durable Gold-owned data and semantic comparison is standardized across deduplication and validation workflows. A single SBERT model version is enforced across offline pipelines and runtime. Detailed rules and invariants are defined in [ADR-P2-013](#p2-key-decisions-adrs)|Semantic authority and runtime contract were conflated in Gold. Gold held embeddings, metadata, and traceability (authority role) and also the lean runtime handoff (contract role). Minor, awkward differences between Silver's validation state and Gold's authority state revealed that ownership belonged upstream, adjacent to where deduplication actually occurs|[Diagram: Iteration 5](../assets/docs/phase2/p2_content_factory_iterations/phase2_dev_aces_iteration_5.jpg)|
|**6**|Consolidate semantic authority at Silver; reduce Gold to a derived mirror|Silver promoted to system-of-record: `master_id` assignment and embedding/metadata ownership moved to Silver (adjacent to `qa_validation` where deduplication occurs). Publisher pipeline removed; Gold becomes a derived handoff mirror (schema-gated projection of Silver), not a promoted artifact anymore. Fine-tuned SBERT commitment relaxed (SLM/LLM judge tier addresses the ambiguous cases fine-tuning would have targeted).|- (terminal). Architecture converged; stabilization and automation follow|[Figure 5](#p2-content-factory-architecture-in-depth)|

**Future consideration (deferred):**
Adding a third path for manually entered questions was considered but postponed. For now manual input is handled as controlled corrections rather than a full ingestion flow.

### Schema evolution & safe change
The core value produced by the Content Factory is the dataset. To keep data quality consistent across new generation batches and updates, a centralized schema is needed. This schema is enforced in the `qa_validation` pipeline as a gatekeeper to the `Silver` dataset. The schema is implemented using Pydantic classes, where:

- New features are introduced as `Optional` fields.
- Backfills are executed using the same enrichment logic as new data, once that logic is promoted from the notebook into a pipeline (second swim lane).
- Once verified, fields are promoted to `Required`.

This approach allows the system to safely upgrade historical data over time, without relying on external scripts or manual re-ingestion.

### How data is managed (Demo scale)

The Content Factory treats data changes and outcomes as four distinct cases:

1. **Creation**: automated synthetic question generation using LLMs.
2. **Validation (filtering)**: automated checks in the `qa_validation` pipeline. Records that fail early checks never enter `Silver`; Semantic checks and embedding generation occur during the `qa_validation` pipeline as part of Silver validation. Semantic embeddings are generated exclusively within the `qa_validation` pipeline during Silver dataset materialization. 
3. **Correction**: manual fixes applied through clear SOPs when accepted data is later found to be wrong.
4. **Removal**: explicit blocking of questions from the `Bronze` data with `kill lists` to prevent known-bad items from re-entering the `Silver` dataset.

Manual intervention is deliberate and controlled. Validation failures are handled automatically, while corrections and removals ensure that previously rejected data does not silently reappear in future runs.

### Scope Boundaries (Phase 2)

To keep Phase 2 focused and avoid premature infrastructure complexity, the following capabilities are intentionally deferred:

- No real-time feature serving
- No formal Feature Store abstraction
- No online learning or user-driven correction loops

## P2 Runtime Environment
The architecture below is the anticipated Phase 2 runtime design. The tracer is currently deployed on the Phase 1 GoTTY/VM setup for quick end-to-end results; the full runtime upgrade is staggered (see below). Figure 6 shows the target design, not the current tracer deployment.

![Phase 2 CLI-MVP deployment scheme](../assets/docs/phase2/phase2_dev_runtime.jpg)
**Figure 6.** Phase 2 CLI-MVP demo target architecture deployed as a container on a serverless cloud platform with logging and github automation.

### Staggered runtime upgrade
The runtime upgrade is deliberately staggered rather than implemented all at once:

1. **Tracer (current)**: Phase 1 GoTTY/VM deployment, reused for speed. It let the end-to-end logic be validated without runtime refactoring.
2. **Next — FastAPI service layer**: the priority upgrade, addressing the two limitations the tracer surfaced, single-session concurrency (GoTTY shares one terminal) and cold-start lag (~30s model load). A FastAPI service enables concurrent sessions and a single warm startup.
3. **Deferred — full operational tooling:** CI/CD automation and cloud logging are deferred until justified by usage. Manual session reports cover observability needs at current demo scale; the added complexity only pays off at meaningful user volume.

### Deferred anticipated upgrades
Detail on the operational tooling deferred in step 3 above:
- **Demo-level CI/CD**: The container extends the Phase 1 implementation with automated docker builds triggered by Git events (e.g. updates to container or application files with Google Cloud Build).
- **Logging and tracking**: Currently manual session reports reviewed periodically in batches. Advanced monitoring and human review workflows are intentionally deferred to Phase 3 and will **only** be added if user activity reaches a meaningful level (e.g. ~ 100+ users / month), where the added complexity becomes worthwhile.

### Setup a data refresh policy
Since the question runs are batched and infrequent from a contained source (HP books), a policy for rebuilding the container is needed to prevent unnecessary build churn. A new deployment is only triggered when significant value is added:
- Batch accumulation gate: The pipeline buffers new questions and only triggers a build when $>50$ validated sets are ready (preventing micro-deployments).
- Schema evolution: Immediate rebuilds for structural changes (new features/columns).
- Critical patching: Ad-hoc rebuilds are permitted only for severe correctness fixes.

## P2 Tracer Feedback & Telemetry

> 🚧 *Section pending — to be populated with consolidated telemetry once a stable 
> baseline is established. This section will present concrete measured results 
> (routing, latency, compute, cost) as the empirical basis for the design constraints.*

## PHASE 3: Optional Runtime Enhancements
**Objective**: Improve perceived game intelligence through optional, controlled use of an SLM or LLM.

Phase 3 is an optional enhancement that adds value by enabling more natural-feeling interactions in the game. This is achieved by introducing GenAI further in a controlled, guided manner and continue keeping the game itself deterministic. The system is modular and integration can be managed at interfaces.

### Options to consider

Because integration is managed at stable interfaces, the options are not mutually exclusive. The system can start with the lowest-burden option and migrate as requirements justify, without re-architecting the runtime.

1. **Distributed microservice** (LLM, SBERT, database as services): when concurrency/scale demands independent scaling.
2. **Isolated edge containers** (local models, upgraded VMs): when data sensitivity prohibits external calls (patented/confidential), or fixed-cost self-containment is needed. This is the path that makes the architecture viable for regulated domains where external APIs are not permitted.
3. **Provider-agnostic API interfacing**: lowest operational burden; LLM interface abstracted from any single provider (not tied to Google), provider becomes a swappable configuration. Viable when data can leave the boundary and per-query cost is acceptable/offset.

### Deciding factors
1. **Primary**: demonstrated need for scale + user interest (is the enhancement even wanted?)
2. **Constraint:** data sensitivity (may rule out external APIs entirely)
3. **Economic**: cost, unless offset by revenue/subscription.


<a name="4-technical-architecture--pattern-mapping"></a>

# 4: Technical Architecture & Pattern Mapping

The architecture evolved iteratively. Since the design is solving issues and bottlenecks commonly seen in data and AI applications (latency, hallucination, cost), mapping the resulting design against established industry patterns serves two purposes:
- *Validation:* The pattern represents recurring system constraints with well-developed solutions.  Arriving at a similar pattern organically confirms the design is heading in the right direction. 
- *Learning*: by identifying the named patterns and where they appear at scale.

## Core idea: offline computation, lean runtime
The core concept for this project is to separate the generation of intelligence from its consumption. Expensive work, generation, validation, and enrichment, happen offline and upstream. The runtime serves precomputed, validated results.

The pattern appears in the table below in specific forms: batch inference (offline generation), materialized views (precomputed serving), feature stores (offline enrichment) — but they share one root idea -> compute ahead of time, serve cheaply at runtime.

| Component | Design Pattern | Industry Parallels | Similarities |
| :--- | :--- | :--- | :--- |
| **Content Factory** | **Batch Inference**<br>(Offline ETL) [[1]](#references) | **Netflix / Spotify**<br>*(Offline generation of recommendations)* | **Shared Constraint: Latency.**<br>SVE pre-computes questions so gameplay is instant. This mirrors how Netflix pre-generates *Discover Weekly* overnight, so users never wait for inference at play time [[2]](#references).  |
| **Context Refinery** | **Feature Store**<br>(offline portion only) [[3]](#references)| **Uber Michelangelo**<br>*(offline Palette Store)* | **Shared Constraint: Context as Features**<br>The Context Refinery tags content with semantic features (themes, entities) ahead of time so the runtime inherits precomputed signals rather than computing them live. This aligns with the *offline portion* of a feature store, it stops short of a full feature store (no online serving layer or registry). The parallel is Uber's Palette Store, which turns raw signals into reusable features offline so dispatch decisions stay fast [[4]](#references). |
| **Runtime Container** | **Immutable Artifact**<br>(Stateless Read / Pre-materialization) [[5]](#references) | **Static prebuilt websites**| **Shared Constraint: Reliability.**<br>The runtime serves a static, versioned, immutable dataset produced upstream. Isolating the read path from the generation path means upstream failures cannot affect the running game. This is the same idea behind serving pre-built static content on websites. |
| **Prefect Workflow** | **DAG Orchestration** [[6]](#references) | **Modern Data Stacks**<br>*(Lyft/DoorDash logistics)* | **Shared Constraint: Data Integrity.**<br>SVE uses DAGs to enforce a tiered, medallion-inspired data flow (Bronze → Silver → Gold → Production). Validation gates promote data between tiers; failures are quarantined before reaching the runtime. This mirrors production ETL pipelines like DoorDash's, where failed validation quarantines records before they propagate downstream. |

---

## References

1. Sapien, “*Batch Inference*”, Sapien AI Glossary. [Online]. Available: https://www.sapien.io/glossary/definition/batch-inference,
2. Netflix Technology Blog, *“Integrating Netflix’s foundation model into personalization applications*,” Medium, Netflix TechBlog. [Online]. Available: https://netflixtechblog.medium.com/integrating-netflixs-foundation-model-into-personalization-applications-cf176b5860eb, refer to discussion of batch inference within the embedding store architecture.
3. Qwak, “Feature store architecture,” Qwak Blog, 2023. [Online]. Available: https://www.qwak.com/post/feature-store-architecture. See *Offline Store* section.
4. J.-H. Chen, A. Chow, J. Faleiro, Y. Liu, and A. Narayan, “Michelangelo: Uber’s machine learning platform,” InfoQ Presentations, 2017. [Online]. Available: https://www.infoq.com/presentations/michelangelo-palette-uber/
5. C. Richardson, “Materialized view pattern,” Medium – Design Microservices Architecture with Patterns, 2019. [Online]. Available: https://medium.com/design-microservices-architecture-with-patterns/materialized-view-pattern-f29ea249f8f8.
6. M. E. Inzaugarat, “What is a DAG? A practical guide with examples,” DataCamp Blog, 2024. [Online]. Available: https://www.datacamp.com/blog/what-is-a-dag.

---