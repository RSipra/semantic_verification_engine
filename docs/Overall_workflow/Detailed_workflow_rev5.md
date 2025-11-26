# Project Workflow & Development Plan

This document outlines the sequential, multi-phase development workflow for the Harry Potter Trivia Game project. The project follows a phased-agile methodology, combining a high-level roadmap with iterative development sprints. Each phase builds upon a tested and refined foundation, allowing for flexibility and the integration of key learnings discovered during development.

## A Note on Agile Practice
While the phases are sequential, the work within them is iterative. Sprints are treated as focused development cycles that include not just building, but also learning, testing, and refactoring. Feedback from user testing (Phase 1.5) and insights gained during complex tasks (like NLP prototyping in Phase 2) directly inform the next steps, ensuring the project remains adaptable and robust.

## Phase 1: Core Game Logic & CLI Foundation
### Sprint 1.1: Environment & Data Foundation
- *Status*: DONE
- *Tasks*: Environment setup, Git initialization, library installation, comprehensive data loading, cleaning, analysis, data ingestion pipeline, and curation.
- *Outcome*: A clean, de-duplicated, feature-rich, high-quality dataset ready for the MVP. A stable project environment.

### Sprint 1.2: Basic Game Loop & OOP Structure
- *Status*: DONE
- *Tasks*: Design initial Game, Question, and Player classes. Implement a basic, non-interactive CLI loop to display questions.
- [Patterns] Learn: Research Separation of Concerns (SoC) and Model-View-Controller (MVC) design principles.
- [Patterns] Design Checkpoint: Before finalizing classes, review how well the design separates data/logic (Model) from the user interface (View).
- [Test] Task: Learn the basics of pytest. Write initial unit tests for core Question methods.
- *Outcome*: A solid OOP structure is defined and core logic is unit tested.

### Sprint 1.3: Answer Checking, Scoring & Core Logic
- *Status*: DONE
- *Tasks*: Implement the first version of answer checking. Refine the game loop to handle turns, scoring, and end-of-game conditions. Finalize Trivia class for loading and sampling questions.
- [Patterns] Learn: Research the Strategy Pattern. This will be crucial for handling different answer-checking methods later.
- [Patterns] Design Checkpoint: Implement a simple, direct string comparison for answer checking initially. Think: "How easy will it be to swap this logic for fuzzy matching or semantic similarity later?" The Game class should orchestrate the check without being tightly coupled to the specific method of checking.
- [Test] Task: Write unit tests for Player state changes (scoring, chances) and Trivia loading/sampling logic.
- *Outcome*: A playable, basic CLI game with a clear win/loss condition.

### Sprint 1.4: Game Controller & Full MVP Loop
- *Status*: DONE
- *Tasks*: Create GameController class. Implement main loop integrating Trivia & Player, handling turns, score/chance updates, basic 'quit', game over conditions.
- [Patterns] Design Checkpoint: Review GameController structure. How does it manage Model objects (Player, Trivia)? How does it handle View (print/input) for now? Revisit Separation of Concerns.
- [Test] Task: Write unit tests for testable logic within GameController (methods not directly using raw I/O). Manual testing for I/O flow initially.
- *Outcome*: Fully functional CLI MVP. Core controller logic unit tested where possible.

### Phase 1.5: Deployment, Testing & Refinement
#### Sprint 1.5.0: User Testing Strategy
- *Status*: ON-HOLD (tested with 2 users on local device)
- *Objective*: Define the audiences and goals for Alpha and Beta testing phases.
- *Alpha Testers (5-20 users)*: Close friends and family, including children aged 10+. Goal is to get initial feedback on fun, basic usability, and question clarity.
- *Beta Testers (Wider Network)*: Friends in professional network and other technical users. Goal is to get feedback on ease of installation/running, code clarity, and more detailed gameplay mechanics.

#### Sprint 1.5.1: Alpha Deployment (Runnable Package & Cloud Environment)
- *Status*: DONE
- *Objective*: Make the functional MVP easily runnable for the Alpha tester group without requiring them to sift through the entire development repository.
- *Tasks*:
    - Structure the project as a proper Python package (using pyproject.toml or setup.py) that includes only the necessary game files (.py scripts, data CSV).
    - Create a distribution package (a wheel file) that can be shared and installed.
    - Update the README.md with simple, clear instructions for two ways to run the game:
        1. Installing the package and running from the command line.
        2. A one-click setup using a cloud environment like GitHub Codespaces, which avoids any local installation for testers.
- *Outcome*: A shareable "Alpha" version that can be easily tested by non-technical and technical users alike.

#### Sprint 1.5.2: Learn Mocking & Test I/O
- *Status*: DONE
- *Tasks* : Learn unittest.mock or pytest-mock. Write automated tests for functions involving direct user I/O (print/input), such as the main game loop in the GameController.
- *Outcome*: Key user interactions are now covered by automated tests, increasing reliability.

#### Sprint 1.5.3: Refactor, Increase Test Coverage & Beta Deployment
- *Statis*: BLOCKED – Needs Replanning (web based cli instead of container)
- *Tasks*:
    - Review all Phase 1 code based on Alpha feedback and testing experience. Refactor parts that were difficult to test.
    - Increase unit test coverage for all core logic modules.
    - Update all documentation and docstrings.
    - **Beta Deployment**: Create a simple Dockerfile to containerize the application. Push the container image to a registry (like Docker Hub or GitHub Container Registry). Update the README.md with simple docker run instructions for Beta testers. Create a formal "Release" on GitHub.
- *Outcome* : A refactored, well-tested, documented, and containerized "Beta" version of the CLI game, providing a solid foundation for the next phases.

## Phase 2: NLP Integration (Data Augmentation & Semantic Features) & Architectural Refinement
### Sprint 2.1: Automated Generation Pipeline & Data Lake
- *Status*: CURRENT
- *Objective*: To enrich and balance the dataset using a semi-automated, multi-step AI pipeline with essential human oversight.
- *Tasks*: Execute the AI question generation pipeline with prompt engineering to create new, high-quality questions, with a focus on adding more 'Explanatory' (EX) type questions to support semantic model training.
    1. Develop a prompt engineering strategy
    2. Experiment with API calls to refine and finalize master prompts for each question type (EX, MCQ, FR) iteratively. Minimize hallucinations and have error checks.

#### 2.1.1: Generation Pipeline & Data Lake
- *Focus*: **Creation & Persistence**
- *Tasks*:
    1. **Develop Generation Script (`generate_questions.py`)**: Build a **Prefect** flow that orchestrates the generation 
    2. **Establish Data Lake**: Configure the `data/08_generated_questions/` directory to store raw, immutable JSONL outputs, separating them from the *Baseline dataset*
    3. **Prepare for SBERT finetuning**: finalize the dataset that will be used for trainign SBERT in later sprints.
- *Outcome*: A production-grade ETL pipeline that can generate thousands of traceable questions overnight without manual supervision. A dataset that can be used to fine-tune a SentenceBert for answer-checking.

#### 2.1.2: QA & Validation Pipeline
- *Focus*: **Quality Assurance & Filtering**
- *Tasks*:
    1. **Develop Validation Script (`pipeline_validation.py`)**: Create a secondary flow that acts as the "Quality Gate."
    2. **Schema Enforcement**: Validate strict typing (using `TypedDict`) on incoming data *before* processing to catch structural errors early (moved upstream from ingestion).
    3. **Semantic De-duplication**: Integrate **SBERT** to detect "Trivia Kernel" redundancy against both the new batch and the existing baseline (Thresholds: 0.95 Auto-Reject, 0.75 Manual Review). 
    4. **Faithfulness Check**: Implement "Source Grounding" verification to flag potential hallucinations where the answer is not supported by the source text.
    5. **Feature matching** update the baseline dataset schema to accomodate new features developed in question generation and then enforce it through pipeline. 
- *Outcome*: a refined "silver" dataset where every question has passed structural, semantic, and factual checks.

#### 2.1.3: Data Ingestion Pipeline
- *Focus*: **Merging & Production**
- *Tasks*:
    1. **Simplified Merge Logic**: A lightweight version of phase 1 that takes only the "approved" records from the QA pipeline, assigns final Game IDs, and appends them to the master dataset in `data/05_final/`.
    2. **Version Control**: Apply dataset tagging (e.g., `v2.0`) to enable rollback capabilities.
    7. Update baseline dataset and keep a separate dataset of just the newly generated questons for fine-tuning SBERT in later sprint.
- *Outcome*:  A larger, more balanced dataset where new questions are generated from AI-sourced facts with citations, then pre-tagged by their likely canonical source, significantly streamlining the final manual verification process.

### Sprint 2.2: Observability & Knowledge Retention (The Shadow Architect)
- *Objective*: To establish a "System Memory" that automatically tracks architectural decisions, technical debt, and codebase evolution, enabling future autonomous agents to understand the legacy system without manual retraining (phase 4)
- *Tasks*:
    1. **Baseline "Digital Archaeology"**: Develop and run a one-off script (`init_memory.py`) that mines the Git history and file structure to reconstruct the project's evolution to date. This creates the initial `docs/SYSTEM_MEMORY.md` "brain."
    2. **The "Shadow Architect" Agent**: Create a lightweight maintenance script (`update_memory.py`) that uses an LLM to analyze uncommitted changes (`git diff`) and append new decisions, architectural shifts, and TODOs to the System Memory.
    3. **Workflow Integration**: Adopt a "Janitor" workflow where the Shadow Architect is run after significant coding sessions but before commits, ensuring the "Why" behind changes is captured in natural language alongside the code.
- *Outcome*: A living `SYSTEM_MEMORY.md` file that serves as the "Long Term Memory" for future agentic workflows.

### Sprint 2.3: NLP Prototyping (Quality Metrics & Entity Resolution)
- *Objective*: To develop the core NLP logic required for the Validation Pipeline and Game Controller, utilizing a **"Gazetteer-First, LLM-Refined"** approach for robust entity resolution without custom model training.
- *Tasks*:
    1. **Gazetteer Construction**: Compile comprehensive lists of high-value terms (Characters, Spells, Locations, flora, fauna, magical objects) from the corpus to serve as a high-precision, low-latency detection layer.
    2. **Entity Resolution Pipeline**: Implement a two-stage entity tagging system for the Validation Pipeline:
        - **Detection**: Use the Gazetteer to instantly flag potential entities in the generated questions.
        - **Canonicalization**: Use an LLM task (Gemini) to map detected terms to their canonical forms (e.g., "Albus" -> "Albus Dumbledore") and classify their roles. This ensures consistent metadata for the future Knowledge Graph.
    3. **Entity Density Scorer**: Implement scoring logic that calculates the density of these resolved entities to serve as a proxy for "Question Complexity" in the Quality Score.
- *Outcome*: A robust entity resolution system ready for integration, enabling high-quality metadata extraction without the overhead of training and maintaining a DistilBERT model.

### Sprint 2.4: Implement Hybrid Answer-Checking
- *Objective*: To create an intelligent and flexible answer-checking system and integrate it into the CLI-game.
- *Methodology*: Implement a Hybrid Answer-Checking Strategy that routes answers to different validation methods based on question_type. For example: 
    - For 'EX' (Explanatory) Questions: Use Sentence-BERT to calculate the cosine similarity between the player's answer and the canonical answer. [Implementation Note]: This will initially be handled via a commercial Embedding API for simplicity and zero maintenance overhead. A future enhancement could involve self-hosting a specialized open-source model (e.g., Sentence-BERT) for greater control. Interesting to explore.
    - For 'FR' & 'MCQ' Questions: Use Fuzzy String Matching (e.g., via thefuzz library) to handle minor typos.
    - For 'YN' & Numeric Questions: Use a direct, normalized string comparison.
- *Tasks*: 
    - Create a modular nlp_engine.py to encapsulate the answer-checking logic.
    - Implement the Hybrid Answer-Checking Strategy that routes answers to different validation methods (Semantic, Fuzzy, Direct Match) based on question_type.
    - Integrate this new engine into the GameController, replacing the simple string comparison.
- [Patterns] Implementation: Implement the Strategy Pattern with an AnswerChecker context class and different strategy classes (SemanticStrategy, FuzzyStrategy, DirectMatchStrategy).
- [Test] Task: Write unit tests for each checking strategy with known correct and incorrect answer variations.
- *Outcome*: A sophisticated answer-checking module that makes the game fairer and more intelligent.

### Sprint 2.5: Sprint 2.5: Cloud Infrastructure & Deployment Design
- *Objective* : To architect and provision the cloud environment that will host the production game and its data, transitioning from local files to a scalable serverless stack at cost (free).
- *Tasks*:
    1. Data Architecture Design (The "Two-Tier" Storage):
     - Operational DB (Firestore): Design the NoSQL document schema for the game app. Create a sync script (sync_to_firestore.py) to push "Gold" JSONL data to Firestore. Rationale: Free tier, JSON-native, fast.
     - Analytical DB (BigQuery): Set up a BigQuery dataset to store raw pipeline logs and run history. Create a loader script to dump your data/07_pipeline_logs for long-term analysis. Rationale: Industry standard for Data Engineering.
    2. "Web-CLI" Containerization:
     - Dockerize the Game: Write a Dockerfile to package your Python game engine into a portable container image.
     - Browser Terminal Adapter: Build a lightweight Flask + xterm.js wrapper. This serves your CLI game to a web browser, allowing anyone to play it instantly without installing Python.
    3. Serverless Deployment (Cloud Run):
     - Deploy the Docker container to Google Cloud Run.
     - Configure it to "Scale to Zero" (so it costs $0 when no one is playing).
- *Outcome*: A live, URL-accessible version of your game (game.your-project.run.app) backed by a real cloud database, ready for users.

### Sprint 2.6: Architectural Refactoring
- *Objective*: To separate the core game engine from the UI, preparing it for multiple frontends (CLI and Web).
- *Tasks*:  separate and abstract.
    - Define an abstract GameView interface using Python's abc module.
    - Refactor the GameController (which now contains all game and NLP logic) to be presentation-agnostic, moving it to a core/ module.
    - Create a views/cli_view.py that implements the GameView interface, extracting all print/input calls from the controller.
    - Update the CLI entry point (main.py) to wire up the new GameController and CLIView.
- [Test] Task: Update all existing unit tests to work with the newly refactored architecture.
- *Outcome*: A cleanly separated architecture where the game engine is independent of the UI.

## Phase 3: Web Application & Deployment
### Sprint 3.1: Flask App & UI
- *Tasks*: Build a basic Flask web application. Create HTML templates for the game interface.
- *Outcome*: A functional web UI where the game can be played in a browser.

### Sprint 3.2: Deployment
- *Tasks*: Prepare the application for deployment (e.g., using Gunicorn, Docker). Deploy to a cloud platform (e.g., Heroku, AWS).
- *Outcome*: A publicly accessible, deployed version of the trivia game.

## Phase 4: Future Enhancements & Moonshots
### Sprint 4.1: Predictive Difficulty Modeling & Adaptive Logic
- *Objective*: To dynamically adjust game difficulty based on player performance and question characteristics.
- *Tasks*:
    - Feature Engineering: Create a feature set for each question using existing data like question_length, answer_length, readability_scores, question_type, and the NER tags generated in Phase 2.
    - Model Training: Train a classification model to predict a difficulty category (e.g., 'Easy', 'Medium', 'Hard') for each question. Tree-based models like Decision Tree or Gradient Boosting (e.g., LightGBM) are strong candidates for this tabular data problem.
    - Integration: Incorporate the trained model into the GameController. The controller will use player performance (e.g., current score, streak) to select questions from the appropriate difficulty category, creating an adaptive experience.
- *Outcome*: A game that can dynamically adjust its difficulty level.

### Sprint 4.2: Knowledge Graph Integration
- *Tasks*: Link questions (via NER tags) to an external knowledge graph (e.g., a custom graph of HP characters, places, and relationships). Implement a feature to "show related facts" after a question is answered.
- *Outcome*: An enriched game experience that offers contextual information beyond the trivia itself.

*Some aspirational ideas to consider. A thought experiment right now in the possibilities of where the game could be taken.*

### Sprint 4.3: Moonshot - Autonomous Content Generation factory
- *Overall Objective*: To build a fully automated, end-to-end MLOps system for generating, validating, and ingesting new trivia questions, evolving from a prompt-based engine to a fully autonomous RAG-powered system. This would likely be carried out in two phases:

**Phase A**:
- *Phase objective*: automate the existing, proven prompt-engineering workflow -> orchestrate the individual data scripts (Generation, QA, Ingestion) into a single, cohesive, end-to-end automated system incorporating professional MLOps practices.
- *Tasks*: 
    1. *Develop a master orchestration script*: create a central workflow manager script that orchestrates the entire data enrichment process. Its logic will sequentially trigger the Question Generation Script, run the QA Scoring Pipeline, pause at a manual approval gate, and upon confirmation, call the final Data Ingestion Pipeline. The script will automatically trigger:
        - The Question Generation Script to create a new batch of raw questions.
        - The QA Scoring Pipeline to enrich the raw data with quality scores and generate a report of flagged items.
        - Implement a manual approval gate: the pipeline will pause after the QA step and present the report, requiring a manual "go/no-go" confirmation from the user before proceeding.
        - Trigger the final ingestion: Upon approval, the script will automatically call the Data Ingestion Pipeline to merge the new, validated data into the main baseline dataset.
    2. *Integrate MLOps for Experiment Tracking*: Enhance the master script by incorporating a formal experiment tracking tool like MLflow or Weights & Biases. This will automate the logging of all experiment parameters, metrics, and output artifacts from the YAML configuration, replacing the manual update process.
    3. *Implement a CI/CD Workflow*: Create a CI/CD pipeline (e.g., using GitHub Actions) that can be configured to automatically trigger the full master orchestration script. This enables automated runs based on events like a push to the main branch or an update to a prompt file.
    4. *Deploy as a Scheduled Service (Stretch Goal)*: As a final enhancement, deploy the entire workflow as a scheduled service (e.g., a cron job or a scheduled GitHub Action) that can automatically enrich the dataset over time.
- *Phase outcome*: A professional, production-grade MLOps system for managing the entire data enrichment lifecycle. The final result will be a single, command-line callable script that turns a multi-step manual process into a streamlined, reproducible, and automated workflow.    

**Some aspirational ideas to consider. A thought experiment right now in the possibilities of where the game could be taken.**

**Phase B: Moonshot** 
- *Phase objective*: To replace the prompt-engineering component of the factory with a more advanced, autonomous RAG (Retrieval-Augmented Generation) system.
- *Tasks*:
    1. Set up a vector database with canonical source texts (e.g., the seven books).
    2. Implement a "Retriever" component to find relevant passages for a given topic or entity.
    3. Implement a "Generator" component that creates questions based only on the retrieved context from the vector database.
    4. Implement an automated "Verifier" AI call to self-check for quality and lore-consistency.
    5. Integrate into the phase A factory. Swap out the old prompt-engineering script in the master orchestrator with new, more intelligent RAG engine.
- *Resource Note*: This step would require significant API usage, potential vector database costs, and more complex engineering compared to the semi-automated approach. Iteresting learning but might be costly. Could put API call caps to keep in free tier. Smaller open source that can run on cpu?
- *Sprint Outcome*: A professional, production-grade MLOps system for managing the entire data enrichment lifecycle, with a clear path for evolving its core generation logic from a static, prompt-based system to a dynamic, RAG-powered one.

### Sprint 4.5: Moonshot - Agentic Quiz Master? 
- *Objective*: To progressively evolve the `GameController` from a simple game engine into a sophisticated, conversational AI Quiz Master with a dynamic, personalized persona. This would likely be done in a phased approach.

**Phase A: Conversational Interface (the MC)**
- *Phase objective*: wrap the existing game logic in a conversational interface (~a super-layer on top of the existing game), turning the game into a playable chatbot (with API calls).
- *Tasks*:
    1. *Develop a Chat UI*: Build a simple chat interface (e.g., within the Flask web app).
    2. *Create a Base Persona*: Design a `system_prompt` that defines the Quiz Master's base personality (e.g., witty, knowledgeable).
    3. *Integrate the Game Engine*: The AI's primary role will be to act as an "MC." It will call the existing GameController to get a question, present it to the player, and pass the player's answer back to the GameController for validation.
- *Phase outcome*: A functional, chat-based trivia game where the AI acts as a simple but engaging host for the core game logic.

**Phase B: Intelligent agent (a "smart MC")**
- *Phase objective*: elevate the AI from a simple host to an autonomous agent that strategically directs the game flow -> Evolve the GameController into an autonomous agent that manages the entire trivia session, plans question sequences based on topic and difficulty, and uses more advanced NL techniques for player interaction.
- *Tasks*: 
- [Architecture]: The agent will be designed with a "Right Tool for the Job" approach, using different models for different tasks: a small, specialized open-source model (e.g., Sentence-BERT) for high-volume semantic answer checking, and potentially larger models or APIs for more complex tasks like conversational hints or on-the-fly question generation. To be explored, this is a whole new project in its own right.
    1. *Expose Game Logic as "tools"*: Refactor the GameController's methods (e.g., select_question, provide_hint) into "tools" that the LLM can choose to call.
    2. *Enhance the Agent's prompt*: Update the system prompt to instruct the agent to manage the trivia session. It will be responsible for deciding when to provide a hint or what kind of question to ask next, using its tools to execute those decisions.
    3. *Establish the Quiz Master's persona with foundational UI/UX*: e.g. Design a custom avatar and a themed UI (parchment, magical fonts). Implement a base conversational tone (e.g., witty, friendly) with lore-specific slang. Create custom interaction elements like a themed typing indicator (e.g., "Consulting the Pensieve...")
    4. **Integrate with other models**: Connect the agent's select_question tool to the *Predictive Difficulty Model* from [Sprint 4.1](#sprint-41-predictive-difficulty-modeling--adaptive-logic), allowing it to make data-driven decisions to adapt the game's difficulty in real-time.
- *Phase outcome*: A more dynamic and intelligent "Quiz Master" AI with a distinct personality that actively manages the gameplay experience by planning question sequences based on topic and difficulty.

**Phase C: Personalized companion (a "Memorable MC" or "friend and fellow HP enthusiast")**
- *Phase objective*: To give the agent long-term memory, enabling a unique personalized and adaptive experience for each player -> integrate a *dynamic adaptive player persona* in .
- *Tasks*:
    1. *Develop a Player profile system*: Create a persistent storage system to track a "Player Profile" for each user, logging performance by theme (e.g., 80% on 'Spells', 30% onf 'Potions'), last played date, and memorable conversation snippets.
    2. *Implement a dynamic system prompt*: Before each game session, generate a dynamic prompt that combines the Quiz Master's base persona with a summary of the current player's profile.
    3. *Enhance the AI persona with adaptive UI/UX*: e.g.  Design UI elements that explicitly reference past events (e.g., a "memory" icon).Adapt the UI in real-time based on player performance (e.g., add a "winning streak" visual effect). Leverage the player profile to generate highly personalized conversational banter.
    4. *Enable personalized gameplay*: Leverage the dynamic prompt to offer personalized greetings, adapt question selection to challenge a player's strengths or reinforce weaknesses, and tailor conversational banter by referencing past interactions.
- *Phase outcome*: A sophisticated and intelligent "Quiz Master" AI that provides a unique, engaging, and personalized trivia experience that evolves with each player through sessions, transforming the game from a simple Q&A bot into an adaptive conversational companion.

### Sprint 4.6: Agentic DevOps & Legacy Modernization
- *Objective*: To deploy specialized AI agents to manage the lifecycle of the project's code itself, ensuring a smooth transition from the manual Python scripts (Phase 2) to fully autonomous systems without "Big Bang" rewrites.
- *Tasks*:
    1.  **Context Injection (System Memory Utilization)**: Configure new DevOps agents to ingest the `docs/SYSTEM_MEMORY.md` established in Phase 2 as their primary context. This allows them to immediately understand legacy constraints (e.g., "Why we use a 0.75 threshold") without re-analysis.
    2.  **The Wrapper Agent (Strangler Fig Pattern)**: Instead of rewriting the working `generate_questions.py` script immediately, build an agent that acts as an API layer for it. The agent parses natural language intent ("Generate 50 hard Potions questions") into the precise CLI arguments (`--tasks EX --category Potions --limit 50`) and executes your legacy script.
    3.  **The Archaeologist Agent**: Use an agent to perform deep retrieval on the historical logs (`data/07_pipeline_logs/`) to answer architectural queries that aren't explicitly in the System Memory.
    4.  **The Safety Net Agent (Test Generation)**: Use an agent to read the "Golden Dataset" (validated JSONL output from Phase 2) and automatically generate a regression test suite. This ensures that as you refactor the pipeline, the new system never performs worse than the old one.
- *Outcome*: A self-maintaining repository where "Legacy Code" becomes a library of tools for the new Agentic system, preserving the value of previous work while enabling rapid evolution.
