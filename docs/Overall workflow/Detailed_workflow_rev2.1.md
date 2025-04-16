# Detailed Workflow with Sprints v.2.1 (Static NER for MVP, NLP before Flask)

### 15 April 2025
---

## Phase 1: Core Game Logic, Unit Testing & Pattern Awareness (CLI Foundation)

### Sprint 1.1: Environment & Data Foundation
* Status: DONE (-> 5 April 2025)
* Tasks: Env setup, Git init, Install base libraries, Load/Clean dataset, Save cleaned data.
* Outcome: Clean dataset ready, project environment setup.

### Sprint 1.2: Basic Game Loop & OOP Structure
* **Status: Current**

* Tasks: Design initial `Game`, `Question` classes; Implement basic CLI loop (display Q, get input).
* `[Patterns]` Learn: Read/watch resources on **Separation of Concerns (Model-View-Controller thinking)**.
* `[Patterns]` Design Checkpoint: Before finalizing classes, review: How well does the design separate data/logic (Model) from print/input (View)? Is the main loop (Controller) cleanly orchestrating? Aim for clear responsibilities.
* **`[Test]` Task:** Learn basics of `pytest` or `unittest`. Write unit tests for `Question` methods (e.g., `check_answer`, `__eq__`).
* Outcome: Basic OOP structure defined, non-interactive CLI display possible. Core `Question` logic unit tested.

### Sprint 1.3: Exact Answer Checking & Scoring (& Player/Trivia Logic)
* Tasks: Implement exact string match logic; Add scoring. Refine game loop (play X questions, show final score). Implement `Player` class (fixing properties, decoupling `find_player_level`). Implement `Trivia` class loading/sampling logic.
* `[Patterns]` Learn: Read/watch resources on the **Strategy Pattern**.
* `[Patterns]` Design Checkpoint: After implementing the simple exact match: *Think* - "How easy would it be to swap this checking logic later? Does my `Game` class make this possible? How might the Strategy pattern help here *eventually*?" (No need to implement Strategy now). Review `Player` & `Trivia` structure.
* **`[Test]` Task:** Write unit tests for `Player` methods & `Trivia` loading logic.
* Outcome: Playable basic CLI game logic complete. Core `Player` & `Trivia` logic unit tested.

### Sprint 1.4: Game Controller & Full MVP Loop
* Tasks: Create `GameController` class. Implement main loop integrating `Trivia` & `Player`, handling turns, score/chance updates, basic 'quit', game over conditions.
* `[Patterns]` Design Checkpoint: Review `GameController` structure. How does it manage Model objects (`Player`, `Trivia`)? How does it handle View (`print`/`input`) for now? Revisit Separation of Concerns.
* **`[Feature Ideation]` Task:** Brainstorm "Easter Eggs" & Themed Commands (e.g., spells for quit/hint). Create initial "Nice-to-Have" feature list for later phases.
* **`[Test]` Task:** Write unit tests for testable logic within `GameController` (methods not directly using raw I/O). Manual testing for I/O flow *initially*.
* Outcome: Fully functional CLI MVP according to the agreed richer scope (Player, chances, levels etc.). Core controller logic unit tested where possible. Initial ideas for fun features documented.

---

## Phase 1.5: Testing, Mocking & Refinement (Solidify Foundation)

### Sprint 1.5.1: Learn Mocking & Test I/O
* Tasks: Learn `unittest.mock` / `pytest-mock`. Write automated tests for `Introduction` methods (`print_ascii_art`, `get_player_details`) and `GameController`'s main loop I/O using mocking.
* Outcome: Key Input/Output interactions are now covered by automated tests. Understanding of mocking achieved.

### Sprint 1.5.2: Refactor & Improve Coverage
* Tasks: Review Phase 1 code based on testing experience. Refactor parts that were hard to test (improve modularity, decoupling, potentially applying patterns). Increase unit test coverage for Phase 1 modules (`trivia.py`, `player.py`, `controller.py`/`game.py`). Update documentation/docstrings.
* Outcome: Phase 1 code is refactored, well-tested, and documented, providing a solid foundation for the next phases.

---

## Phase 2: NLP Integration (NER Offline Tagging & Feature Implementation)

*(Moved from original Phase 3 & Modified for Static NER)*

### Sprint 2.1: Annotation - Guidelines & First Batch
* Tasks: Finalize guidelines; Annotate data subset.
* Outcome: Annotated data for NER training.

### Sprint 2.2: NER Model Training (DistilBERT Fine-tuning)
* Tasks: Set up Hugging Face; Write/run training script; Save model.
* Outcome: Custom fine-tuned NER model.

### Sprint 2.3: Offline NER Tagging & Data Integration
* Tasks: Write/run script to load trained NER model and process the *entire* dataset offline, generating NER tags for each question. Save the enriched dataset (e.g., new CSV/JSON with a `ner_tags` column/field). Modify `Question` class `__init__` and `Trivia` loader to load/store these pre-computed tags.
* `[Patterns]` Learn: Read/watch resources on the **Facade Pattern**.
* `[Patterns]` Design Checkpoint: *Think* - "Could a Facade simplify the interface to the *offline* NER processing script or the loading/handling of the tagged data?".
* Outcome: Full dataset is enriched with static NER tags; `Question`/`Trivia` classes can access them. **No runtime model loading needed yet.**

### Sprint 2.4: Implementing Features Using Static Tags in CLI
* Tasks: Add CLI mechanism for topic selection. Modify `GameController` / `Trivia` to filter questions based on the pre-computed `ner_tags` stored in `Question` objects. Implement basic difficulty estimation rules based on stored `ner_tags`.
* `[Patterns]` Design Checkpoint: Review the **Strategy Pattern** again. Is the filtering/difficulty logic implemented cleanly?
* Outcome: CLI game uses static NER tags for topic selection and/or difficulty. Data science skills demonstrated via features.

---

## Phase 3: Basic Web App (Flask)

*(Moved from original Phase 2)*

### Sprint 3.1: Flask Fundamentals
* Tasks: Install Flask; Create minimal app structure; Set up basic routes (/, /game); Run dev server.
* `[Patterns]` Design Checkpoint: Review **Separation of Concerns/MVC**. Plan how Flask routes (Controller) will interact with your tested Phase 1/2 Model (including accessing NER tags) and HTML templates (View).
* Outcome: Running local Flask server with basic pages.

### Sprint 3.2: HTML Templates & Forms
* Tasks: Create HTML templates (index.html, game_question.html); Implement answer submission form.
* Outcome: Web UI structure in place.

### Sprint 3.3: Integrating Game Logic Backend
* Tasks: Connect Flask routes to tested Phase 1/2 Model (`GameController` logic or Model classes); Handle form submissions; Check answers; Update score/state (using Flask `session`?); Integrate features using static NER tags (like topic selection) into the web UI.
* `[Patterns]` Implementation Checkpoint: Ensure **MVC separation** planned in 3.1 is followed. Keep game logic out of routes; use the Model effectively.
* Outcome: Game playable via web browser, including features based on static NER tags.

### Sprint 3.4: Basic Styling & Deployment Prep
* Tasks: Add simple CSS; Create `requirements.txt`.
* `[Patterns]` Learn: Read/watch resources on the **Observer Pattern**.
* `[Patterns]` Design Checkpoint: *Think* about Observer for potential dynamic UI updates later.
* Outcome: Slightly polished web app, ready for potential sharing.

---

## Phase 4: Enhancements (Future Sprints)

* *(Examples - Prioritize and add detail based on Phase 1 Ideation)*
* **(Example) Sprint 4.A: Implement Runtime NLP & Semantic Answer Checking**
    * Tasks: Implement loading of DistilBERT model/tokenizer at runtime (e.g., in an NLP Service/Facade). Integrate DistilBERT embeddings for checking answer similarity. Refactor answer checking logic.
    * `[Patterns]` Implementation: Implement the **Strategy Pattern** to allow switching between "Exact Match" and "Semantic Match" checking. Implement **Facade Pattern** for runtime NLP service if not done earlier.
* **(Example) Sprint 4.B: Implement Easter Eggs & Themed Commands**
    * Tasks: Implement detection logic for specific commands/keywords (e.g., spells) in user input (potentially using NLU - see Phase 4+ Ideas). Add corresponding unique responses/actions (e.g., alternative quit, hints, hidden messages). Test thoroughly.
* **(Example) Sprint 4.C: Add GUI Enhancements (e.g., dynamic score update)**
    * Tasks: Use JavaScript or other techniques for dynamic UI in Flask app.
    * `[Patterns]` Implementation: Potentially implement the **Observer Pattern** to decouple score updates from UI rendering.
* **(Example) Sprint 4.D: Implement Game States (Menu, Playing, End Screen)**
    * Tasks: Design distinct UI screens and transitions in Flask app.
    * `[Patterns]` Implementation: Potentially implement the **State Pattern** to manage game states cleanly.

---

## Phase 4+ Further Enhancement Ideas (Leveraging DistilBERT/NLP)

* **(Idea) Natural Language Understanding (NLU) of Player Input:** Fine-tune DistilBERT for Intent Classification to understand commands like "hint", "repeat", "I don't know", "what's my score?" beyond just checking the answer. (Requires runtime model).
* **(Idea) Smarter Hint Generation:** Use DistilBERT embeddings (along with NER tags) to find concepts related to question/answer entities and offer more contextual hints. (Requires runtime model).
* **(Idea) Context-Aware Moderator Responses:** Use NLU results or other game state triggers to select from varied, pre-written moderator responses. (Full generation likely needs other models).
* **(Idea) Adaptive Difficulty:** Use player performance combined with NLP features (static NER tags, maybe difficulty classification) to dynamically adjust question difficulty.
* **(Idea) Knowledge Graph Integration:** Use static NER tags to link questions to an external HP knowledge graph, display related facts, or generate follow-up questions.

## Future vision & stretch goals
These are larger, long-term features that may be explored in future development cycles:
- Multiplayer mode (PvP) – Compete with friends or other players
- Auto-generated trivia using LLMs – Dynamically create new questions tailored to theme and difficulty
- “Ask Dumbledore” conversational bot – A mentor-style assistant for hints, lore, or even wisdom
- Gamification elements – XP, house points, badges, level progression, or themed rewards
- Game data analytics for performance / dashboard.

----
### Notes on revision update:
1.	Developed with the assistance of Google Gemini 2.5 pro (experimental) model with a clear prompt to help strategize, support, and help incorporate learning opportunities into the project.
2.	Based on “Detailed_workflow_rev2.docx” -> reorder to have NLP as phase 2 and web app as phase 3 to be able showcase a balance of foundational python / OOP and data science skills in the portfolio before moving to web interface (showstopper). Add stages for ideation and feature development of easter eggs and themed commands. Separated NLP work into static NER tagging and runtime DistilBERT use.
3. Going forward, the workflow will be maintained only in the markdown file.

----
