# My Testing Journey: Notes & Key Learnings
## 1. Why Test and Why pytest?
The goal of automated testing is to create a "safety net" for our code. It allows us to make changes and refactor with confidence, knowing that if we accidentally break something, our tests will fail and tell us exactly where the problem is.

While Python has a built-in unittest framework, we chose pytest for several key reasons:

- Less Boilerplate: Tests are just simple functions (e.g., def test_something():), not large classes that must inherit from unittest.TestCase.
- Plain assert Statements: pytest uses the standard Python assert keyword, which is simple and direct. It provides incredibly detailed feedback on failures automatically.
- Powerful Fixtures: pytest's fixture system is a powerful and clean way to set up reusable test data and environments.

## 2. The Foundation: Testing Simple "Model" Classes
Testing the smaller classes (Player and Question) was relatively straightforward. Since they are primarily data containers and don't depend on external files, we could test them in isolation easily. The main tool we used here was the @pytest.fixture, which allowed us to create a single, reusable instance of an object (like default_player) that could be passed into any test that needed it. This kept our tests clean and followed the DRY (Don't Repeat Yourself) principle. 
Leasons learnt:
- Setting up the test: Act, Assign, Arrange.
- The mindset: test using external methods primarily unless an internal method is crtical to the code.


## 3. The Challenge: Testing the Trivia Class & Mocking
Testing the Trivia class was more complex because its _load_dataset method has external dependencies: it needs to access the file system to read a CSV file. Unit tests should be fast and reliable, and should not depend on external systems. The solution was mocking: temporarily replacing a real function with a fake, controllable "stunt double."

- The Problem: The Problem: The complications began when we tried to refactor repeated @patch decorators into a single, reusable fixture. This led us to use mocker to mock the with resources.as_file(...) statement, which proved difficult because it's a special "context manager." This complexity was the source of persistent errors. After several iterations, the final solution was to come full circle and use individual @patch decorators on each test. While slightly repetitive, this made each test's dependencies explicit and much easier to debug.
    - The Iteration: Our initial goal was to mock importlib.resources (which finds the file) and pandas.read_csv (which reads it). We ran into several persistent errors trying to mock the with resources.as_file(...) statement.
    - Why the with Statement Was a Problem: A with statement uses a special object called a "context manager." Mocking this is tricky because you have to mock its special __enter__ and __exit__ methods. Our attempts to configure a MagicMock for this were complex and causing the persistent FileNotFoundError deep inside Python's libraries.

- The Breakthrough: We realized the best solution was to refactor the application code to make it easier to test. We changed the line in _load_dataset from with resources.as_file(...) to with pkg_data_path.open('r') ..., which was much simpler. This allowed us to use a more straightforward mock on just pd.read_csv, completely solving the problem. This was a key lesson: sometimes you should refactor your code to make it more testable.

Leasons learnt:
- don't over engineer the fixtures / KISS
- With bigger classes - the idea is not to test every method in a class but use scenarios and edge-cases from a user / external perspective. These should inherently be able to test for the internal logic / methods.

## 4. The int vs. int64 Discovery
After fixing the mocks, our tests started failing with a new error: `TypeError: Expected int but found int64`.
- Why was this happening? This was another critical discovery. pandas is built on NumPy and uses its own efficient data types, like numpy.int64, for number columns. Our test, however, was correctly checking if the type was a standard Python int. The isinstance(value, int) check was correctly failing because int64 is not the same as int.
- The Solution: This led to a major design improvement. We decided that the _load_dataset method should be responsible for all data cleaning. We added logic to it to explicitly convert the original_question_id column to a standard Python int (.apply(int)) and to parse all the stringified list columns into real lists (.apply(safe_eval)).
- The Benefit (SoC): This made _load_dataset the single source of truth for clean data. All other methods, like _load_questions, could now be simplified because they could trust that the DataFrame they received was already clean and validated, with all the correct Python data types. This was a perfect example of how the testing process directly leads to a better, cleaner application architecture.

Key learnings: 

- Ultimately, the process of writing unit tests provided more than just a safety net; it forced a granular examination of the code, revealing subtle bugs and leading directly to a more robust and well-designed architecture.
- the safety net - so if logic changes are made to the methods later .. the game logic can safely and quickly checked with the automated tests scripts.
- testing has led to refactoring and moving logic that helped gameflow with simplified helper functions and better understanding of when and where to place validation checks e.g. "fail fast" by checking as early as possibly (when called rather then when used). The refactoring also meant i only had to check external methods to check internal methods. - made that separation cleaner.
- tangential learning - curious how different aspects are handled in real-life scenarios and teams. Developer vs. dedicated tester. Code review vs. testing and overall workflow, determining optimum team sizes.
- testing Trivia class was harder / more involved than the simpler Question / Player classes. It really made me think more deeply about the steps in the code and it's flexibility. Made mistakes in testing - had to iterate to get out out if (e.g. mocking file acceess). more refactoring / logic checking here in comparison. I'm guessing there will be more with the View and Controller classes that have greater interdependencies?
- shift in mindset: so testing is checking if the code can handle the unexpected ... how it would behave in scenarios that could happen while its running... its' not checking the actual code.
You are right. When you write a unit test, you are not checking the code line-by-line like a proofreader. Instead, you are acting like a scientist.
- You create a specific, controlled scenario (the "Arrange" part).
- You run an experiment by calling your code (the "Act" part).
- You observe the behavior and check if the result matches your hypothesis (the "Assert" part).
So, while the test executes the actual code, its focus is entirely on the external behavior.

The "Black Box" Analogy
Think of your Player class as a sealed, black box.
- You can't see the internal wiring (_score, _chances_left).
- You can only interact with the buttons and screens on the outside (the public methods like add_score() and properties like .score).
A good unit test treats the class like this black box. It presses a button (player.add_score()) and then checks the screen (assert player.score == 1) to see if the behavior was correct. It doesn't care how the internal wiring made that happen.

This is why we test the public methods and not the private ones. We are testing the contract—what the class promises to do—not the internal implementation details.

- tension between future-proofing (and making sure each unit is robust enough for future changes and tests) and pragmatic for MVP (redunant checking code) ... e.g. adding data validation to each helper stage of the start() method. - it comes down to a design decision ... 1. defensive programming - each method is standalone and can run with untrusted data 2. Centralized validation (_load_dataset is the strict gatekeeper) allowing for simpler helper methods - in tandem with supporting "pipeline" validation checks in the start() method between transition to the next internal helepr method. --> assembly line approach. Not planning on using the internal methods on their own. testing logic for the other helper is with the understanding that _load_dataset is the gatekeeper and has been rigorously tested for it - so assume clean data and look for other operational edge cases.
For _load_questions: no longer testing for bad data types, am testing the sampling logic. The edge cases are:
- Requesting more questions than available: Does it correctly raise a ValueError?
- Requesting 0 questions: Does it correctly produce an empty list of Question objects?
- Requesting all available questions: Does it correctly sample all questions from the DataFrame?

For _create_question_objects: no longer testing for missing keys or malformed data. You are testing the object creation logic. The edge cases are:
- Happy Path: Does it correctly convert a list of dictionaries into a list of Question objects?
- Empty List: Does it correctly handle being given an empty list [] and return an empty list [] without crashing?
- Session ID assignment: Does it correctly assign sequential session_ids (1, 2, 3...) to the created objects?

### Notes about using patches in Trivia tests:

The @patch decorators automatically pass in mock objects as arguments to the test function, from the bottom decorator up.

The two @patch decorators intercept the two separate file system calls:
1. The 'resources.files' patch silences the file *finding* step to prevent a FileNotFoundError.
2. The 'pd.read_csv' patch intercepts the file *reading* step.
This allows the test to configure the mock_read_csv object to return the fake DataFrame from the fixture.

There must be a parameter in the function signature to "catch" each mock. (mock_read_csv, _mock_resources, mock_filename etc). If a specific test doesn't need to configure a mock, then the name of its parameter is given a leading underscore (e.g., _mock_resources) to signal that it's intentionally unused.

## Testing philosophies:
1. Code-driven development: aka "test-after-development" --> We focused on writing the application code first. We built the Player, Question, Trivia, View, and Controller classes to get a functional, end-to-end "happy path" working. Now, we are going back and writing the automated tests to create a "safety net" and guide our refactoring. Best case for MVP. "Code-First" approach is often better for:
- Exploratory Prototyping (Your MVP): When you're not sure what the final design will be and you're just trying to get something working to see how it feels, TDD can be too rigid. Your approach of building the "happy path" first was perfect for this stage.
- UI-Heavy Work: It's often difficult to write a test for "does this look good?" before you've built it. Visual design is often more iterative.

2. Test-driven development: This is the opposite approach. With TDD, you would have started by writing a failing test before you had any application code. For example:
    - Step 1 (Red): Write test_player_initialization() and run it. It would fail because the Player class doesn't even exist yet.
    - Step 2 (Green): Write the minimum possible Player class to make that one test pass.
    - Step 3 (Refactor): Clean up the code.
Then you would repeat the cycle for the next feature, like add_score. 
You would typically use a Test-Driven Development (TDD) approach when:

1. The Logic is Complex and Critical
This is the classic use case. If you are writing a piece of code where a small logical error could have significant consequences, TDD is invaluable.
- What it is: Core algorithms, financial calculations, complex state management, or critical validation logic.
- Why TDD helps: It forces you to define the correct behavior in a test before you write the complex implementation. You focus on the "what" before the "how." For example, the logic in your Player.get_rank_category() method, with its specific percentage thresholds, would have been a perfect candidate for TDD. You would write a test for the "Novice" case first, then write just enough code to make it pass, then write the test for "Enthusiast," and so on.

2. The Requirements are Very Clear and Specific
When you have a very clear "spec" or set of rules, TDD is a great way to turn those rules into an "executable specification."
- What it is: A feature with a clear set of inputs and expected outputs. For example: "A password must be at least 8 characters, contain one uppercase letter, and one number."
- Why TDD helps: Each requirement becomes a test case. The test suite acts as living documentation of the rules. When all the tests pass, you know you have met all the requirements.

3. You are Designing an API or Library for Others
When you're building a class that other parts of your code (or other developers) will use, TDD forces you to think from the consumer's perspective.
- What it is: Designing a class's public interface (like your Trivia class).
- Why TDD helps: You start by writing a test that shows how you wish you could use the class. This helps you design a clean and intuitive API. For example, you might write assert trivia.get_session_questions() before the method even exists, which helps you realize that's a much cleaner interface than accessing an internal attribute.

4. You Need to Refactor Old, Untested Code
This is a very common and powerful use of TDD. When you have a piece of "legacy" code that you need to change but are afraid to break, you don't start by changing it.
- What it is: Safely changing old code.
- Why TDD helps: You first write tests that characterize the existing behavior. You write tests that pass with the old code. This creates a safety net. Now you can refactor the internal implementation with confidence, and as long as your tests still pass, you know you haven't broken anything.

In summary, TDD is a discipline you apply when correctness and clear design are more important than initial speed, especially for the critical, logical core of your application.

## 4. Testing GameView class - user facing.
You're not testing complex calculations or state changes. Instead, your goal is to answer one simple question:
>"When I call this method, does it print the correct text to the screen?"

Since we can't "see" the screen in an automated test, we need a special tool that can "listen" to the terminal and capture everything that gets printed.

### The Tool: The capsys Fixture
pytest has a wonderful built-in fixture for this called capsys (short for "capture system output"). It's a "magic" fixture that records everything sent to standard output (stdout, where print and console.print go).

### How to Test a Display Method (e.g., display_welcome)
Here is the standard pattern for testing a method that just prints things:
- Arrange: Create an instance of your GameView.
- Act: Call the display method you want to test (e.g., view.display_welcome()).
- Capture: Use capsys.readouterr() to get the text that was just printed.
- Assert: Check that the captured text contains the key phrases you expect.

Example Test:
# In a new file: tests/unit/test_view.py

from HPtrivia_game.view import GameView

def test_display_welcome(capsys):
    """Tests that the welcome message is printed correctly."""
    # ARRANGE
    view = GameView()

    # ACT
    view.display_welcome()

    # CAPTURE & ASSERT
    captured = capsys.readouterr()
    assert "Welcome to the Harry Potter Trivia Game!" in captured.out

### A Practical Strategy for Testing Your View
You don't have to test everything at once. You can prioritize the tests based on how complex the method is. Here's a good order to follow:

1. Test the "Smart" Methods First (Most Important):
 - Methods with Logic & Formatting: Start with methods that take data and format it, like display_final_score, display_welcome_for_player, and display_roast. These are the most likely to have bugs.
 - Methods with if/else branches: Your give_feedback method has two different outputs. You should write two separate tests: one that passes is_correct=True and one that passes is_correct=False, and assert that the correct text is printed in each case.

2. Test the Input Methods Next (Also Critical):
 - Write tests for get_player_name, get_player_house, and prompt_for_replay.
 - For each one, you'll need to test the "happy path" (the user enters valid input) and the "unhappy path" (the user enters invalid input a few times before entering a valid one). This will prove your validation loops work. You'll use mocker.patch('rich.console.Console.input', ...) for this.

3. Test the Simple Static Methods Last (Good to Have):
 - Finally, you can write simple tests for methods like display_welcome and display_dedication. These tests are less critical because the methods are so simple, but they are good for creating a complete test suite.

So,s to summarize: Yes, you should aim to have a test for every user-facing message. Start with the most complex ones and work your way down to the simplest.


1. Testing the "Smart" Methods First
Your approach to first test methods with logic, formatting, and conditional branches (if/else) is spot on. These are the most critical parts of the View as they directly process data from the Model or Controller.

How capsys fits in: This is the primary tool for this stage. You'll call your "smart" methods like display_final_score(score) or give_feedback(is_correct=True) and then use capsys.readouterr() to assert that the output is formatted exactly as you expect.

Example Test for give_feedback:

Python

# test_view.py
import pytest
from your_game_module import GameView

def test_give_feedback_when_correct(capsys):
    """Tests the feedback message for a correct answer."""
    view = GameView()
    view.give_feedback(is_correct=True)
    captured = capsys.readouterr()
    assert "Brilliant! You got it right!" in captured.out
    assert "Wrong!" not in captured.out

def test_give_feedback_when_incorrect(capsys):
    """Tests the feedback message for an incorrect answer."""
    view = GameView()
    view.give_feedback(is_correct=False, correct_answer="Wingardium Leviosa")
    captured = capsys.readouterr()
    assert "Oh no! The correct answer was Wingardium Leviosa." in captured.out
2. Testing the Input Methods Next
This is another critical step, and your distinction between the "happy path" and "unhappy path" is key to writing resilient code.

How monkeypatch fits in: This tool is essential here. For the "unhappy path," you need to simulate a user entering invalid data followed by valid data. monkeypatch can be configured to return a sequence of different values on consecutive calls to input().

Example Test for an Input with Validation ("Unhappy Path"):

Let's assume your get_player_house method keeps asking until the user enters a valid Hogwarts house.

Python

# test_view.py
def test_get_player_house_with_invalid_input_then_valid(monkeypatch, capsys):
    """
    Tests that the view re-prompts after invalid input and 
    returns the first valid input.
    """
    view = GameView()
    # Simulate user typing "Muggle", then "Slytherin"
    inputs = ["Muggle", "Slytherin"]
    monkeypatch.setattr('builtins.input', lambda _: inputs.pop(0))
    
    house = view.get_player_house()
    
    # 1. Assert the final output is the valid one
    assert house == "Slytherin"
    
    # 2. Assert the user was re-prompted with an error message
    captured = capsys.readouterr()
    assert "Invalid house. Please try again." in captured.out
3. Testing Simple Static Methods Last
You're right, these are the lowest priority but are important for achieving 100% test coverage and ensuring consistency in your game's messaging.

How capsys fits in: This is again the tool of choice. These tests are usually very simple: call the method and assert that the expected static text is present in the captured output.

Example Test for display_welcome:

Python

# test_view.py
def test_display_welcome_message(capsys):
    """Tests that the static welcome message is displayed correctly."""
    view = GameView()
    view.display_welcome()
    captured = capsys.readouterr()
    assert "Welcome to the Harry Potter Trivia Challenge!" in captured.out
Summary
Your strategy is effective because it's risk-driven. By testing the most complex and logic-heavy parts of your GameView first, you catch the most significant potential bugs early. It ensures your core functionality works before you spend time on simpler, less error-prone methods.

Pairing this logical approach with the technical tools pytest provides—capsys for output and monkeypatch for input—gives you a complete and professional testing plan for your CLI View. 👍

------

got tangled in the interconnections - MVC and SOC helps --> cheatsheet:

Here is a breakdown of the responsibilities specifically for your Harry Potter trivia game.

**The Model: The Brains & Data**
The Model knows all the game's rules and holds all the data, but it doesn't know how to display anything.

*Player class is your Model:*
- Responsible for: Holding the player's name, house, and score. It also contains the logic for calculating the rank (find_player_wizard_rank).
- Asks: "What is my score?" or "What is my rank?"

*TriviaManager / Question classes are your Model:*
- Responsible for: Holding the list of questions, knowing the correct answer for each, and providing a new question when asked.
- Asks: "What is the next question?" or "Is this answer correct?"

*The View: The Face*
The View is responsible for everything the user sees and types. It's "dumb" about the rules; it only does what the Controller tells it to do.
GameView class is your View:
- Responsible for: Printing questions, displaying feedback ("Correct!"), showing the final score, and getting input (get_player_name, get_player_answer).
- It should never decide if an answer is correct or change the score.

*The Controller: The Manager*
The Controller is the "traffic cop" that connects the Model and the View. It directs the entire flow of the game.
GameController class is your Controller:

Responsible for:
- Telling the Model (TriviaManager) to get a question.
- Telling the View (GameView) to display that question.
- Telling the View to get the player's answer.
- Asking the Model if the answer is correct.
- Telling the Model (Player) to update the score if correct.
- Telling the View to show the "Correct!" or "Incorrect!" feedback.
- Deciding when the game loop ends.

*Main: The assembler* : the main function is acting as the "assembler" for your application
it uses a common and powerful software design pattern called Dependency Injection.
Instead of the GameController creating its own dependencies (the Trivia object), you are creating the dependency in main and "injecting" it into the controller.

This has two major benefits:
1. Easier Testing: When you unit test your GameController, you don't have to use a real Trivia object that reads from a CSV file. You can create a simple, fake "mock" Trivia object and pass that into the controller instead. This makes your controller tests much simpler and faster.
2. Flexibility: If you ever decide to get trivia questions from a website API instead of a CSV, you could create a new TriviaFromAPI class. The only place you'd need to change your code is in main.py; the GameController wouldn't need to be touched at all because it's decoupled from how it gets the trivia data.
-------------------------
-- > GameView testing -- refactored get_random_feedback_from_key() to be more generalized... default message returned by the message using it. 
instead of it giving a message that did not fit all context.


testing _get_user_input() when checking unhappy (quit) path --> led to refactoring --> create a general utility to clean strings (strip, lower, remove punctuations) - also used by check_answer method to standardize the player raw reesponse and correct answer for a fairer, more flexible answer checking. Also refactored prompt_to_save_report use utils method for processing str. ask_game_renew as well.
---------------

### Blog Point: How a Simple Test Uncovered a Subtle Bug
Here are two options for your blog post:

Paragraph Version
A crucial "happy path" test for our "save report" feature unexpectedly failed. The test simulated a realistic user input of "YES ! ", but our clean_input_string() utility function processed it into "yes ", with a lingering space. This caused the check if 'yes ' in ('y', 'yes') to fail. The bug revealed that the order of operations in our cleaning function was vital. By refactoring the utility to strip whitespace last—after handling case and punctuation—we created a much more robust function. It was a perfect example of how testing with realistic, slightly messy data exposes subtle flaws and leads to more resilient code.

Bullet Point Version
- The Goal: Test the "happy path" for the "save report" feature.
- The Test: Simulate a realistic user input like "YES ! ".
- The Failure: The test failed because our clean_input_string() utility incorrectly processed the input into "yes ", leaving a trailing space.
- The Refactor: We fixed the utility by changing the order of operations, ensuring .strip() was called last to remove any whitespace left over after punctuation removal.
- The Lesson: Testing with realistic, imperfect data is critical. It uncovers subtle bugs in seemingly correct code and forces you to build more resilient and user-friendly logic.

### A Note on Future-Proofing: Proactive Technical Debt

An interesting discovery during testing the View class was to learn about the best way to test console output from the rich library. A failing test for our "save report" feature initiated a valuable chain reaction; while the initial bug was in a small helper method, the investigation led to a deeper scrutiny of our assertions and ultimately uncovered the limitations of using pytest's capsys fixture with the rich library.

While pytest's standard tool, capsys, is working perfectly for all of my tests right now, I learned that its interaction with rich can sometimes be unpredictable. To ensure the test suite remains 100% stable and "future-proof," I've made a note to refactor these tests to a more robust pattern using Python's io.StringIO. It’s a great example of proactive technical debt management—choosing to improve a part of the codebase to prevent potential issues, even before they've occurred!

CONTROLLER TEST
- strategy: scenario based on state of game.
- More OOP! using classes to organize files. Use inheritance to use the same setup method for tests along with common setup methods to make testing simpler and reduce repetitive parts.
- using `.assert_called_once()`, `.assert_called_once_with(parameter)`, and `.assert_not_called()` for testing method calls in the controller
- _handle_game vs. run_game... core unit test = _handle_game and run_game is a higher-level integration test. Testing different logic.
- got to try out and learn about advanced testing techniques, including:
    - autouse fixtures for shared setup.
    - Mocking dependencies (View, Trivia) to achieve true unit test isolation.
    - Using side_effect to simulate exceptions (UserWantsToQuit, IOError).
    - Using pytest.raises to verify that exceptions are correctly propagated.
    - Patching internal methods, constants, and external libraries (pyfiglet, datetime, filesystem calls).

Integration tests to consider:
1. run game (a single game run)
differnt scenarios plus smooth transition to endgame - e.g. at quitting, no chances left, happy path
2. full game / main - different scenarios
    - Goal: Test the entire application flow with a real Controller and a real Player and Trivia model, only mocking the user-facing GameView.
    - How: This is a step up from your controller unit tests. You would create a real Controller with a real Trivia model. You would still mock the GameView to automatically provide user answers. This test verifies that the real Model and real Controller work together correctly for a full game.
3. data loading from csv
    - Goal: Verify that your Trivia model can correctly parse your actual MVP_TRIVIA_CSV_NAME file.
    - How: Write a test that creates a real Trivia object with your real CSV file and asserts that questions are loaded without errors and have the correct structure. This tests the integration between your Model and your data source.
