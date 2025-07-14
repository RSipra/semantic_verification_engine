# Project Workflow & Development Plan

This document outlines the sequential, multi-phase development workflow for the Harry Potter Trivia Game project. The strategy is to build a robust foundation by first creating a high-quality, curated dataset and a functional Command-Line Interface (CLI) MVP. Subsequent phases will then build upon this foundation to integrate advanced NLP features and deploy a full-featured web application.

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
- *Status*: CURRENT
- *Tasks*: Create GameController class. Implement main loop integrating Trivia & Player, handling turns, score/chance updates, basic 'quit', game over conditions.
- [Patterns] Design Checkpoint: Review GameController structure. How does it manage Model objects (Player, Trivia)? How does it handle View (print/input) for now? Revisit Separation of Concerns.
- [Test] Task: Write unit tests for testable logic within GameController (methods not directly using raw I/O). Manual testing for I/O flow initially.
- *Outcome*: Fully functional CLI MVP. Core controller logic unit tested where possible.

### Phase 1.5: Deployment, Testing & Refinement
#### Sprint 1.5.0: User Testing Strategy
- *Objective*: Define the audiences and goals for Alpha and Beta testing phases.
- *Alpha Testers (5-20 users)*: Close friends and family, including children aged 10+. Goal is to get initial feedback on fun, basic usability, and question clarity.
- *Beta Testers (Wider Network)*: Friends in professional network and other technical users. Goal is to get feedback on ease of installation/running, code clarity, and more detailed gameplay mechanics.

#### Sprint 1.5.1: Alpha Deployment (Runnable Package & Cloud Environment)
- *Objective*: Make the functional MVP easily runnable for the Alpha tester group without requiring them to sift through the entire development repository.
- *Tasks*:
    - Structure the project as a proper Python package (using pyproject.toml or setup.py) that includes only the necessary game files (.py scripts, data CSV).
    - Create a distribution package (a wheel file) that can be shared and installed.
    - Update the README.md with simple, clear instructions for two ways to run the game:
        1. Installing the package and running from the command line.
        2. A one-click setup using a cloud environment like GitHub Codespaces, which avoids any local installation for testers.
- *Outcome*: A shareable "Alpha" version that can be easily tested by non-technical and technical users alike.

#### Sprint 1.5.2: Learn Mocking & Test I/O
- *Tasks* : Learn unittest.mock or pytest-mock. Write automated tests for functions involving direct user I/O (print/input), such as the main game loop in the GameController.
- *Outcome*: Key user interactions are now covered by automated tests, increasing reliability.

#### Sprint 1.5.3: Refactor, Increase Test Coverage & Beta Deployment
- *Tasks*:
    - Review all Phase 1 code based on Alpha feedback and testing experience. Refactor parts that were difficult to test.
    - Increase unit test coverage for all core logic modules.
    - Update all documentation and docstrings.
    - **Beta Deployment**: Create a simple Dockerfile to containerize the application. Push the container image to a registry (like Docker Hub or GitHub Container Registry). Update the README.md with simple docker run instructions for Beta testers. Create a formal "Release" on GitHub.
- *Outcome* : A refactored, well-tested, documented, and containerized "Beta" version of the CLI game, providing a solid foundation for the next phases.

## Phase 2: NLP Integration (Data Augmentation & Semantic Features) & Architectural Refinement
### Sprint 2.1: Curator-Assisted Dataset Expansion
- *Objective*: To enrich and balance the dataset using a semi-automated, multi-step AI pipeline with essential human oversight.
- *Tasks*: Execute the AI question generation pipeline with prompt engineering to create new, high-quality questions, with a focus on adding more 'Explanatory' (EX) type questions to support semantic model training.
    1. Fact & Source Generation (AI Call #1): Prompt a generative model to create a list of facts on specific topics, instructing it to provide a source citation (e.g., book name or chapter reference) for each fact.
    2. Streamlined Human Verification: Use the AI-provided source citation to quickly and efficiently verify the accuracy of each fact against the canonical material. Discard any facts that are incorrect or have a dubious source.
    3. Question Generation (AI Call #2): For each verified fact, prompt the model to create a well-phrased question (FR, MCQ, etc.), preferably requesting a structured output like JSON for easy parsing.
    4. Source Classification (AI Call #3): For each generated Q&A pair, use a specialized AI prompt to classify the likely canonical source of the information (e.g., 'Book-Canon', 'Movie-Canon', 'Unclassified-NonCanon'). This will create a lore_source tag for each new question.
    5. Prioritized Final Review: Manually review the AI-generated questions, prioritizing those flagged as Unclassified-NonCanon to ensure all questions meet quality and lore-accuracy standards before adding them to the main dataset.
- *Outcome*:  A larger, more balanced dataset where new questions are generated from AI-sourced facts with citations, then pre-tagged by their likely canonical source, significantly streamlining the final manual verification process.

### Sprint 2.2: NLP Prototyping in Notebooks
- *Objective*: To develop and validate the core NLP models in a dedicated data science environment before application integration.
- *Tasks*: This will two main components (NER & Semantic answer checking)
    1. **Hybrid NER Model**: In a Jupyter Notebook, develop a hybrid NER pipeline.
        - Step 1 (Gazetteer Pass): Compile comprehensive lists (gazetteers) of known entities (characters, spells, places). Use these lists for a high-precision first pass of entity tagging.
        - Step 2 (Model Pass): Annotate a data subset (can be accelerated by the gazetteer pass) and fine-tune a DistilBERT model to identify entities based on context.
        - Step 3 (Precedence Rule): Define a clear rule of precedence: gazetteer matches are considered the "source of truth" and always take priority. The DistilBERT model is then used to find entities not present in the gazetteers and to resolve ambiguities.
        - Once the dataset is tagged, use NER tagging for categorization (theme, difficulty) for gameplay (e.g. Only spells, characters, difficulty level etc).
    2. Hybrid Checker: In a separate notebook, prototype the two-tiered answer checker: fuzzy matching for short answers and Sentence-BERT with cosine similarity for long answers. Create pre-processed Sentence-Bert correct answer embeddings for game play
- *Outcome*:  Two validated NLP models, with the notebooks serving as detailed portfolio pieces showcasing the data science process.

### Sprint 2.3: Implement Hybrid Answer-Checking
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

### Sprint 2.4: Offline NER Tagging & Feature Integration
- *Tasks*: Fine-tune a DistilBERT model for custom Harry Potter entities. Run the trained model over the entire dataset offline to generate and save NER tags for each question. (Free GPU access with Google Colab?)
- *Outcome*: The dataset is enriched with NER tags, enabling features like topic-based question selection without runtime model loading.

### Sprint 2.5: Architectural Refactoring
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

### Sprint 4.3: Moonshot - Autonomous Content Generation (RAG Pipeline)?
- *Objective*: Evolve the semi-automated pipeline from Sprint 2.1 into a fully autonomous RAG (Retrieval-Augmented Generation) system that can be integrated into the AI Quiz Master.
- *Tasks*:
    1. Set up a vector database with canonical source texts (e.g., the seven books).
    2. Implement a "Retriever" component to find relevant passages for a given topic.
    3. Implement a "Generator" component that creates questions based only on the retrieved context.
    4. Implement an automated "Verifier" AI call to self-check for quality and lore-consistency.

    *Resource Note*: This step would require significant API usage, potential vector database costs, and more complex engineering compared to the semi-automated approach. Iteresting learning but might be costly. Could put API call caps to keep in free tier. Smaller open source that can run on cpu.
- *Outcome*: An agentic system capable of generating new, verified trivia on demand.

### Sprint 4.3: Moonshot - Agentic Quiz Master? 
- *Tasks*: Evolve the GameController into an autonomous agent that manages the entire trivia session, plans question sequences based on topic and difficulty, and uses more advanced NLU for player interaction.
- [Architecture]: The agent will be designed with a "Right Tool for the Job" approach, using different models for different tasks: a small, specialized open-source model (e.g., Sentence-BERT) for high-volume semantic answer checking, and potentially larger models or APIs for more complex tasks like conversational hints or on-the-fly question generation. To be explored, this is a whole new project in its own right.
- *Outcome*: A more dynamic and intelligent "Quiz Master" AI.