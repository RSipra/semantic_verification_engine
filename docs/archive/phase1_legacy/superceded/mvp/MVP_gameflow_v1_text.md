# Trivia Game Logic Flow (List[Question] Approach)

**Design decision**: change in how individual questions are handled in the game session

This document outlines the step-by-step logic flow and interactions between the `Trivia`, `Question`, and `Controller` classes, assuming the `Trivia` class manages a list of fully formed `Question` objects. 

A flowchart [here](MVP_gameflow_v1_flowchart_view.svg) explains the gameflow, described below, graphically.This is generic right now and does not use actual class and method names. As code is developed, this will be updated to match.

**Assumed Classes & Key Responsibilities:**

* **`Trivia`:** Manages loading the dataset (CSV -> DataFrame) and preparing the session-specific `List[Question]` objects. Holds `self.questions: List[Question]`.
* **`Question`:** Represents a single question (likely a dataclass). Holds data (`question_id`, `session_id`, `question_text`, `correct_answer`, `keywords`). Contains the `check_answer(player_answer: str) -> bool` method.
* **`Controller`:** Orchestrates the game flow. Manages turns, interacts with `Trivia` to get questions, interacts with `Question` objects to display/check, handles player input/output (View role), and manages game state (score).
* **`Player` (Implied):** Holds player-specific state like score.
* **`View` (Implied):** Handles presentation (printing to console) and input gathering (`input()`). Logic often resides within `Controller` methods in simple CLI apps.

---

## 1. Initialization Phase

*( In main script, `main.py`)*

1.  **Create `Trivia` instance:**
    * Code: `` `trivia = Trivia(csv_filename="path/to/data.csv")` ``
    * *Parameter:* `csv_filename` (`str`) - Path to the data file.
    * *Internal:* `Trivia.__init__` stores the filename. `self.questions` is initially `None`.

2.  **Create `Player` instance (Optional but common):**
    * Code: `` `player = Player(name="User")` ``
    * *Parameter:* `name` (`str`, optional).
    * *Internal:* Stores player state, score initialized (e.g., 0).

3.  **Create `Controller` instance:**
    * Code: `` `controller = GameController(trivia_manager=trivia, player=player)` ``
    * *Parameters:*
        * `trivia_manager` (`Trivia` instance)
        * `player` (`Player` instance, optional)
    * *Internal:* `Controller.__init__` stores references

---

## 2. Game Setup Phase

*(Triggered by `main` calling a method like `controller.setup_game()` which performs setup first)*

1.  **`Controller` triggers data loading by calling `trivia_manager.start()`:**
    * *Parameters:* None (uses instance's internal state).
    * *Action:* This initiates the data loading and `Question` object creation within the `Trivia` instance.

2.  **`Trivia.start()` Executes:**
    * Calls `self._load_dataset()`:
        * Finds the CSV file using `self.data_csv_filename`.
        * Reads the CSV into `self.trivia_df` (pandas DataFrame).
        * Sets `self.data_csv_path`.
        * Handles potential `FileNotFoundError`, `pandas` parsing errors.
    * Calls `self._load_questions()`:
        * Samples `n` rows from `self.trivia_df` into `session_df` (DataFrame).
        * Converts `session_df` into `session_dicts` (`List[Dict]`) using `to_dict(orient='records')`.
        * Calls `self._create_question_objects(session_dicts)`:
            * *Parameter:* `session_dicts` (`List[Dict]`).
            * *Internal Loop:* Iterates through `session_dicts` using `enumerate` to get index `i` and dictionary `q_dict`.
            * *Internal Action (per dict):*
                * Parses data from `q_dict` if needed (e.g., converting keyword string to list).
                * Instantiates a `Question` object: `` `q_obj = Question(question_id=q_dict['id'], ..., session_id=i + 1)` ``. Maps dictionary keys to `Question` attributes.
                * Appends `q_obj` to a temporary list.
            * *Returns:* The completed `List[Question]`.
        * Assigns the returned list to `self.questions`. **`Trivia` now holds the `List[Question]`**.

3.  **`Controller` state updated:** The `Controller` knows setup is complete. It can now proceed to the gameplay loop. Display Introduction.
4. Controller uses thes `Introduction` class to greet the player and get details that will be used to instantiate the `Player` object for the session.
---

## 3. Gameplay Loop Phase

*(Occurs within a method `controller.run_game()`)*

1.  **`Controller` retrieves the prepared questions:**
    * Code: `` `session_questions = self.trivia_manager.get_session_questions()` ``
    * *Parameters:* None.
    * *Returns:* `List[Question]`.
    * *Error Check:* Controller should verify `session_questions` is not empty/`None`.

2.  **`Controller` initializes loop state:**
    * Resets score if needed: `self.player.score = 0` or `self.current_score = 0`.

3.  **`Controller` iterates through the `session_questions` list:**
    * Code: `` `for current_question_object in session_questions:` ``

4.  **Inside the Loop (Handling One Turn):**
    * **a. Get Current Question:** The loop variable `current_question_object` holds the `Question` object for the turn.
    * **b. Display Question (View Logic):**
        * `Controller` accesses attributes of `current_question_object`.
        * Example Output: `print(f"Question {current_question_object.session_id}: {current_question_object.question_text}")`
    * **c. Get Player Input (View Logic):**
        * Code: `` `player_input = input("Your answer: ")` ``
        * *Returns:* `player_input` (`str`).
    * **d. Check Answer:**
        * `Controller` calls the method *on the `Question` object*:
            * Code: `` `is_correct = current_question_object.check_answer(player_answer=player_input)` ``
            * *Parameter:* `player_answer` (`str`).
            * *Internal:* `Question.check_answer` performs the comparison (`player_input.lower()` vs `self.correct_answer.lower()`).
            * *Returns:* `is_correct` (`bool`).
    * **e. Provide Feedback & Update State (View Logic + Controller Logic):**
        * If `is_correct`:
            * `print("Correct!")`
            * `self.player.add_score(1)` or `self.current_score += 1`
        * Else:
            * `print(f"Incorrect. The answer was: {current_question_object.correct_answer}")` (Accesses attribute for feedback).
    * **(Loop continues to the next `Question` object)**

---

## 4. Game End Phase

*(Occurs after the gameplay loop finishes in `controller.run_game()`)*

1.  **Loop Completes:** All questions in `session_questions` have been processed.
2.  **`Controller` Displays Final Results (View Logic):**
    * Accesses final score (`self.player.score` or `self.current_score`).
    * Accesses total questions (`len(session_questions)`).
    * Example Output: `print(f"\nRound Over! Your final score: {final_score} / {total_questions}")`
3.  **`Controller` Handles Next Steps:**
    * Prints goodbye message.
    * (Future MVP+): Could ask the player if they want to play again.

---

## Summary of Key Interactions

* `main` -> `Trivia(filename)`: (*Param:* `str`)
* `main` -> `Controller(trivia, player)`: (*Params:* `Trivia`, `Player`)
* `Controller` -> `trivia.start()`: (*Params:* None) -> Populates `trivia.questions` with `List[Question]`.
* `Controller` -> `trivia.get_session_questions()`: (*Params:* None; *Returns:* `List[Question]`)
* `Controller` -> (View - Print): Accesses `question_object.session_id`, `question_object.question_text`.
* `Controller` <- (View - Input): Gets `player_input` (`str`).
* `Controller` -> `question_object.check_answer(player_answer)`: (*Param:* `str`; *Returns:* `bool`)
* `Controller` -> (View - Print): Feedback messages, accesses `question_object.correct_answer`.
* `Controller` -> `player.add_score(points)`: Updates player state (if applicable).

## Changes from MVP gameflow rev.0

The initial approach considered using a session dictionary of the session questions in the Trivia object. 

### Summary of Alternative Approach & Rationale for Change
**Alternative Approach**: Trivia holds `List[Dict]`, Question objects are temporary
This approach was considered during planning:

1. Initialization: Same as the chosen approach (Trivia, Player, Controller instances created).
2. Game Setup (Trivia.start): Trivia loads the dataset, samples the DataFrame, and converts the selected rows directly into a `List[Dict]`. This basic list of dictionaries is stored in Trivia.questions. No Question objects are created or stored by Trivia during setup.
3. Gameplay Loop (Controller.run_game):
    - The Controller manages the current question index (i).
    - Each turn, the Controller retrieves the dictionary for the current question from Trivia (e.g., q_dict = trivia.questions[i]).
    - The Controller then uses the Question class to instantiate a temporary Question object from that dictionary (e.g., temp_q = Question(q_dict)).
    - The Controller uses this temp_q object's attributes (question_text) and the loop index (i+1) for displaying the question number and text.
    - After getting player input, the Controller calls the check_answer method on the temporary object (temp_q.check_answer(player_input)).
    - The Controller provides feedback, updates score, and increments its index i. The temp_q object is typically discarded.
4. Game End: Same as the chosen approach (display final score).

**Rationale for Choosing the `List[Question]` Approach Instead**

While the `List[Dict]` approach above might seem simpler initially by reducing the work done in Trivia.start, the `List[Question]` approach (the one chosen and detailed in the flowchart) was preferred for these reasons, especially considering the learning goals of OOP/MVC/SoC:

- Stronger OOP Encapsulation: The chosen approach allows Trivia to manage a collection of fully realized Question objects. Each object properly bundles its data (text, answer, ID) and its behavior (check_answer method), which is a core principle of object-oriented design.
- Clearer Class Roles & SoC: It promotes a clearer separation of concerns.
    - `Trivia`: Prepares and provides domain objects (`List[Question]`).
    - `Question`: Encapsulates its own data and validation logic.
    - `Controller`: Orchestrates the game flow using these complete objects. In the `List[Dict]` approach, the Controller takes on the added task of temporary object creation each turn, slightly blurring the lines.
- Cleaner Controller Logic: The Controller's main loop becomes simpler: get the object, use the object's attributes, call the object's methods. This contrasts with the `List[Dict]` approach's loop: get the dictionary, create a temporary object, use the temporary object.
- Better Represents Domain: Managing a list of Question objects within Trivia provides a more intuitive and object-oriented representation of the game's state ("a trivia session contains Questions") compared to managing a list of generic dictionaries.

Therefore, despite the upfront work in Trivia to convert dictionaries to Question objects, the `List[Question]` approach leads to a design that arguably better demonstrates object-oriented principles and separation of concerns for the rest of the application lifecycle.

**A side-by-side comparison:**

| Feature             | Chosen Approach (`List[Question]`)                  | Alternative Approach (`List[Dict]` + Temp Objects)         |
|---------------------|-----------------------------------------------------|-----------------------------------------------------------|
| **`Trivia` State** | Holds `List[Question]` (rich objects)               | Holds `List[Dict]` (simple data)                          |
| **Object Creation** | All `Question` objects created upfront in `Trivia`  | `Question` objects created temporarily, one per turn      |
| **`Question` Role** | Data holder + Logic encapsulation (persistent)      | Converter + Logic encapsulation (temporary)               |
| **`Controller` Gets**| Fully formed `Question` object                      | Raw `dict` data (then uses `Question` class to wrap it)   |
| **Encapsulation** | Stronger (Data + Behavior together in `Trivia` list)| Weaker (Behavior (`check_answer`) separated until needed) |
| **Initial Complexity**| More work in `Trivia` (Dict -> Object conversion) | Less work in `Trivia` (just `to_dict`)                    |
| **Runtime Complexity**| `Controller` directly uses object                   | `Controller` manages dict retrieval + temp obj creation |
| **Memory** | All objects in memory upfront                       | Only one temp object at a time (plus `List[Dict]`)        |

---
