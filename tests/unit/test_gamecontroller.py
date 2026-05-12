"""
Unit tests for the GameController class and its methods in the HPtrivia_game package.
"""
# pylint: disable=redefined-outer-name, protected-access
# pylint: disable=attribute-defined-outside-init
from unittest.mock import Mock, patch
import pytest
# import all modules for Controller
from game_app.game_controller import GameController
from game_app.player import Player
from game_app.trivia_manager import Question
import game_app.constants as const

# NOTE on Controller Testing & Mocks:
# ------------------------------------
# To test the Controller's orchestration logic in isolation, its dependencies
# (the Model and View) are replaced with mock objects. This allows us to verify
# that the Controller calls the right methods without needing the real objects.
#
# - `mocker`: The pytest fixture that acts as a tool or "factory" for managing mocks.
# - `MagicMock`: The actual "stunt double" object that pretends to be a real class.
#
# Two main patterns are used:
# 1. Creating standalone fakes: We use `mock_view = mocker.MagicMock()` to create a
#    fake object from scratch and pass it into the Controller.
# 2. Patching existing functions: We use `mocker.patch('time.sleep')` to find and
#    replace a real function with a mock for the duration of a test.

# NOTE on testing strategy:
# ------------------------------------
# Unit Testing is based on game states:
# - Start game (Introduction)
    # 1. happy path (data loaded and introduction presented, ready for game session)
    # 2. unhappy path: player wants to quit before player initialized in Introduction
# - Run game
    # 1. happy path (a single question - with correct answer using _handle_turn)
    # 2. unhappy path (a single question - with incorrect answer)
    # 3. Edge case (wrong answer with 0 chances left)
    # 4. Player wants to quite instead of answering question
# - End Game
    # 1. happy path (end game and get score)
    # 2. happy path (end game but play another round)
    # 3. unhappy path (ending after quitting)
    # 4. Edge case - user wants to save report
# Integration tests: TODO
#   # run_game  

## --- FIXTURES ---
#Base Setup Class
class TestGameControllerBase:
    """A base class to handle common setup for all controller tests."""

    @pytest.fixture(autouse=True)  # <- decorator to run this before every test
    def setup_method(self, mocker):
        """
        This fixture runs automatically before every test in any class
        that inherits from this one. It creates a real controller but
        with mocked dependencies.
        """
        # 1. Create mock objects for the dependencies
        self.mock_trivia = mocker.MagicMock()
        self.mock_view = mocker.MagicMock()

        # 2. Create the real controller, injecting the mock model
        self.controller = GameController(self.mock_trivia)

        # 3. Replace the controller's real view with the mock view
        self.controller.view = self.mock_view    

    @pytest.fixture
    def mock_question(self):
        """Mock Question object."""
        question = Mock(spec=Question)  # creates a mock object w. attributes of Question class
        question.check_answer.return_value = True  # behaves like a correct answer
        question.correct_answer = "Correct Answer" # mock correct answer text
        return question

    @pytest.fixture
    def mock_player(self):
        """Mock Player object."""
        player = Mock(spec=Player)
        player.name = "Harry"
        player.house = const.House.GRYFFINDOR
        player.chances_left = 3
        return player

## --- STATE 1: START GAME ---
class TestStartGame(TestGameControllerBase):  # inherit base class for setup to avoid repeating
    """Tests for the start_game() method and introduction sequence."""

    # 1. happy path: verifies the introduction runs, all expected view methods are called, 
    # and the player object is created correctly.
    @patch('HPtrivia_game.constants.NUM_QUESTIONS_PER_SESSION', 3)
    def test_start_game_happy_path(self, mock_player):
        """
        GIVEN a user provides a name and house
        WHEN start_game() is called
        THEN the player is created and the intro sequence is shown.
        """
        # Arrange: Configure the mock view's return values
        self.mock_view.get_player_name.return_value = mock_player.name
        self.mock_view.get_player_house.return_value = mock_player.house

        # Act
        result = self.controller.start_game()

        # Assert
        assert result is True
        # Assert the controller's state was updated
        assert self.controller.player is not None
        assert self.controller.player.name == "Harry"
        # Assert the view methods were called (orchestration check)
        self.mock_view.print_ascii_art.assert_called_once_with(font_style='ogre')
        self.mock_view.print_dedication.assert_called_once()
        self.mock_view.print_greeting.assert_called_once()
        self.mock_view.get_player_name.assert_called_once()
        self.mock_view.get_player_house.assert_called_once()
        self.mock_view.print_personalized_player_welcome.assert_called_once()
        self.mock_view.explain_gameplay.assert_called_once_with(3)

    # 2. unhappy path: verifies the UserWantsToQuit exception is handled correctly when the user 
    # quits during the introduction.
    def test_start_game_when_user_quits(self):
        """
        GIVEN a user doesn't provide a name or house
        WHEN start_game() is called
        THEN the player quits during the intro sequence
        """
        # Arrange
        self.mock_view.get_player_name.side_effect = const.UserWantsToQuit
        # Act & Assert: Verify that the expected exception is raised
        with pytest.raises(const.UserWantsToQuit):
            self.controller.start_game()
        # assert that the player was NOT created
        assert self.controller.player is None

## --- STATE 2: RUN GAME ---
class TestGameSession(TestGameControllerBase):
    """Tests for the run_game() method and gameplay loop."""

    # 1. happy path(correct answer): tests a single turn where the answer is correct, and asserts
    # that player.add_score() and view.give_feedback(is_correct=True, ...) are called.
    def test_handle_turn_happy_path(self, mock_player, mock_question):
        """
        GIVEN a player and a question with a correct answer
        WHEN the controller handles the turn
        THEN the player's score is increased and correct feedback is given.
        """
        # Arrange
        self.controller.player = mock_player
        self.mock_view.get_player_answer.return_value = "Correct Answer"
        mock_question.check_answer.return_value = True 
        mock_question.correct_answer = "Correct Answer"

        # Act
        self.controller._handle_turn(mock_question)

        # Assert
        self.mock_view.display_question.assert_called_once_with(mock_question)
        self.mock_view.get_player_answer.assert_called_once()
        mock_question.check_answer.assert_called_once_with("Correct Answer")
        self.controller.player.add_score.assert_called_once()
        self.controller.player.lose_chance.assert_not_called()
        self.mock_view.give_feedback.assert_called_once_with( True,
                                                             mock_question.correct_answer,
                                                             chances_left=self.controller.player.get_chances)

    # 2. unhappy path (incorrect answer): tests a single turn where the answer is incorrect, and
    # asserts that player.lose_chance() and view.give_feedback(is_correct=False, ...) are called.
    def test_handle_turn_with_wrong_answer(self, mock_player, mock_question):
        """
        GIVEN a player and a question with a incorrect answer
        WHEN the controller handles the turn
        THEN the player's score is not increased, loses a chance, and correct feedback is given.
        """
        # Arrange
        self.controller.player = mock_player
        self.mock_view.get_player_answer.return_value = "Wrong Answer"
        mock_question.check_answer.return_value = False
        mock_question.correct_answer = "Correct Answer"

        # Act
        self.controller._handle_turn(mock_question)

        # Assert
        self.mock_view.display_question.assert_called_once_with(mock_question)
        self.mock_view.get_player_answer.assert_called_once()
        mock_question.check_answer.assert_called_once_with("Wrong Answer")
        self.controller.player.add_score.assert_not_called()
        self.controller.player.lose_chance.assert_called_once()
        self.mock_view.give_feedback.assert_called_once_with(False,
                                                             mock_question.correct_answer,
                                                             chances_left=self.controller.player.get_chances)

    # 3. unhappy path (user quits): mocks view.get_player_answer to raise UserWantsToQuit and
    # asserts that the run_game method catches it and exits gracefully.
    def test_handle_turn_when_user_quits(self, mock_player, mock_question):
        """
        GIVEN a player who has entered a command to quit
        WHEN the controller handles the turn
        THEN the exception to quit is raised correctly.
        """
        # Arrange
        self.controller.player = mock_player
        self.mock_view.get_player_answer.side_effect = const.UserWantsToQuit

        # Act
        with pytest.raises(const.UserWantsToQuit):
            self.controller._handle_turn(mock_question)

        # Assert
        self.mock_view.display_question.assert_called_once_with(mock_question)
        self.mock_view.get_player_answer.assert_called_once()
        mock_question.check_answer.assert_not_called()
        self.controller.player.add_score.assert_not_called()
        
    # Unhappy path: trivia data file not found during session setup
    def test_setup_session_when_csv_file_not_found(self):
        """
        GIVEN the csv file is missing
        WHEN _setup_session is called
        THEN it raises an exception and returns None
        """
        # Arrange: configure the mock trivia manager to raise an exception
        error = FileNotFoundError("File not found")
        self.mock_trivia.start.side_effect = error
        # Act
        result = self.controller._setup_session(3)
        # Assert
        assert result is None
        self.mock_view.display_error.assert_called_once_with(
            f"Could not set up the trivia data. {error}"
        )
    # Unhappy path: run game when the player has not been initialized.
    def test_run_game_with_no_player(self):
        """
        GIVEN no player has been created on the controller
        WHEN run_game() is called
        THEN it should return False and display the 'no player' error message.
        """
        # Arrange
        self.controller.player = None
        # Act
        result = self.controller.run_game()
        # Assert
        assert result is False
        self.mock_view.display_error.assert_called_once_with(
            "Cannot play a round without a player. Please start the game first."
        )

    # Unhappy path: run game when there is no trivia data file
    def test_run_game_when_csv_file_not_found(self, mock_player, mocker):
        """
        GIVEN the csv file is missing
        WHEN run_game is called
        THEN it prints warning and returns False
        """
        # Arrange
        self.controller.player = mock_player
        mocker.patch.object(self.controller, '_setup_session', return_value=None)
        # Act
        result = self.controller.run_game()
        # Assert
        assert result is False
        self.mock_view.display_error.assert_called_once_with(
            "Could not load questions for the session."
        )
        
## --- STATE 3: END GAME ---

class TestEndGame(TestGameControllerBase):
    """Test of the end game methods."""
    ## --- Fixtures for class -------
    # common setups for end_game refactored to make tests Arrange setups simpler
    # and easier to read:
    def _setup_end_game_mocks(self,
                              mock_player,
                              score: int,
                              expected_rank: const.Rank, 
                              will_replay: bool, 
                              will_save:bool):
        """Helper method to configure mocks for the end game sequence."""
        # Arrange
        # common mocks
        self.controller.player = mock_player
        self.controller.player.score = score
        # flexible mocks that can be changed with tests
        self.mock_view.ask_game_renew.return_value = will_replay 
        self.mock_view.prompt_to_save_report.return_value = will_save
        # other common mocks
        self.controller.player.find_player_wizard_rank.return_value = expected_rank

    # sample session_report data to be saved
    @pytest.fixture
    def sample_session_report_data(self):
        """ Provides a sample dictionary for the session report."""
        return {
            "session_id": "some_id",
            "questions": [
                {"question_text": "Q1?", "correct_answer": "A1"},
                {"question_text": "Q2?", "correct_answer": "A2"}
            ]
        }    

    ## --- Unit tests for Class --- 
    
    # Verifies the main summary sequence is displayed and the method returns False
    # when the user chooses not to play again.
    def test_end_game_happy_path_no_replay(self, mock_player):
        """
        GIVEN player and game session has ended and does not want to replay
        WHEN _end_game is called
        THEN method returns False and end sequence messages are displayed
        """
        # Arrange
        total_questions = 3
        expected_rank = const.Rank.MASTER
        self._setup_end_game_mocks(
            mock_player,
            score=3,
            expected_rank=expected_rank,
            will_replay=False,
            will_save=False
        )
        # Act
        result = self.controller._end_game(total_questions)
        # Assert
        self.mock_view.display_game_over.assert_called_once()
        self.mock_view.display_final_score.assert_called_once_with(3, total_questions)
        self.mock_view.display_player_rank.assert_called_once_with(expected_rank, mock_player)
        self.mock_view.display_final_housepoints.assert_called_once_with(3, mock_player)
        assert result is False

    # Verifies the main summary sequence is displayed and the method returns True
    # when the user chooses to play again.
    def test_end_game_happy_path_with_replay(self, mock_player):
        """
        GIVEN player and game session has ended and wants to replay
        WHEN _end_game is called
        THEN the method returns True 
        """
        # Arrange
        total_questions = 3
        expected_rank = const.Rank.MASTER
        self._setup_end_game_mocks(
            mock_player,
            score=3,
            expected_rank=expected_rank,
            will_replay=True,
            will_save=False
        )
        # Act
        result = self.controller._end_game(total_questions)
        # Assert
        assert result is True
    
    # Verifies the conditional logic that calls the internal _save_session_report 
    # method when the user says "yes".    
    def test_end_game_happy_path_with_session_report_saved(self, mock_player, mocker):
        """
        GIVEN player and game session has ended, no replay, and wants to save report
        WHEN _end_game is called
        THEN the method returns False and the session report is saved
        """
        # Arrange
        total_questions = 3
        expected_rank = const.Rank.MASTER
        self._setup_end_game_mocks(
            mock_player,
            score=3,
            expected_rank=expected_rank,
            will_replay=False,
            will_save=True
        )
        # mock save method call
        mock_save_report = mocker.patch.object(self.controller, '_save_session_report')
        # Act
        result = self.controller._end_game(total_questions)
        # Assert
        assert result is False
        mock_save_report.assert_called_once()
    
    # Verifies the guard clause that handles the edge case where no player object exists.
    def test_end_game_with_no_player(self):
        """
        GIVEN player has not be initialized 
        WHEN _end_game is called
        THEN error message is printed and it returns False
        """
        # Arrange
        total_questions = 3
        error_msg = "No player data available to show a final score."
        self.controller.player = None
        # Act
        result = self.controller._end_game(total_questions)
        # Assert
        assert result is False
        self.mock_view.display_error.assert_called_once_with(error_msg)
    
    # Verifies that the controller correctly gets the data from the trivia manager and
    # attempts to write it to a file.
    def test_save_session_report_happy_path(self, sample_session_report_data, mocker):
        """
        GIVEN there is session data to save
        WHEN _save_session_report is called
        THEN it should attempt to write the data to a timestamped JSON file
        """
        # Arrange
        self.mock_trivia.get_session_report_data.return_value = sample_session_report_data
        
        # mock the time to get a predictable timestamp
        mock_datetime = mocker.patch('HPtrivia_game.game_controller.datetime')
        # mocking a call chain with two methods - so two return values / one for each method
        mock_datetime.now.return_value.strftime.return_value = "2025-07-30_17-00-00"
        # mock file access
        mock_path_obj = mocker.MagicMock()
        mock_path = mocker.patch('HPtrivia_game.game_controller.Path', return_value=mock_path_obj)
        # mock the built-in 'open' function and the 'json.dump' function
        mock_file_open = mocker.patch('builtins.open', mocker.mock_open())
        mock_json_dump = mocker.patch('HPtrivia_game.game_controller.json.dump')
        
        # Act
        self.controller._save_session_report()
        
        # Assert
        mock_path.assert_called_once_with("reports")
        mock_path_obj.mkdir.assert_called_once_with(exist_ok=True)
        # Verify the file was opened with the correct, predictable filename
        expected_filepath = mock_path_obj / "trivia_session_2025-07-30_17-00-00.json"
        mock_file_open.assert_called_once_with(expected_filepath, 'w', encoding='utf-8')
        # Verify json.dump was called with the correct data and file handle
        mock_json_dump.assert_called_once_with(
            sample_session_report_data,
            mock_file_open(), 
            indent=4,
            ensure_ascii=False
        )
    # Verifies the guard clause that handles the case where there is no session data to save.
    def test_save_session_report_with_no_data(self, mocker, capsys):
        """
        GIVEN the session report is empty
        WHEN save_session_report is called
        THEN it should print a debug message and exit early.
        """
        # Arrange
        self.mock_trivia.get_session_report_data.return_value = {}
        mock_path = mocker.patch('HPtrivia_game.game_controller.Path')
        mock_open = mocker.patch('builtins.open')
        # Act 
        self.controller._save_session_report()
        captured = capsys.readouterr()
        # Assert
        self.controller.trivia_manager.get_session_report_data.assert_called_once()
        assert "DEBUG: No questions in session, skipping report." in captured.out
        mock_path.assert_not_called()
        mock_open.assert_not_called()
    
    # Test report saving with file I/O error.
    def test_save_session_report_file_error(self, mocker):
        """
        GIVEN a file system error will occur
        WHEN _save_session_report is called
        THEN the error is caught and a message is displayed to the user.
        """
        # Arrange
        mock_open = mocker.patch('builtins.open')
        mock_datetime = mocker.patch('HPtrivia_game.game_controller.datetime')
        mock_datetime.now.return_value.strftime.return_value = "2024-01-01_12-00-00"
        mock_open.side_effect = IOError("Permission denied")
        self.controller.trivia_manager.get_session_report_data.return_value = {"test": "data"}
        # Act
        self.controller._save_session_report()
        # Assert
        self.controller.view.display_error.assert_called_once_with("Could not save session report: Permission denied")  # type: ignore

    # happy path: verifies that the personalized goodbye message is displayed when a player exists.
    def test_display_goodbye_with_player(self, mock_player):
        """
        GIVEN a player and the player name
        WHEN display_goodbye is called
        THEN a personalized goodbye message is printed
        """
        # Arrange
        self.controller.player = mock_player
        # Act
        self.controller.display_goodbye()
        # Assert
        self.mock_view.display_goodbye.assert_called_once_with(self.controller.player.name)

    # unhappy path: verifies that the generic goodbye message is displayed when no player
    # was created.
    def test_display_goodbye_no_player(self):
        """
        GIVEN the player is not initialized
        WHEN display_goodbye is called
        THEN a generic goodbye message is displayed
        """
        # Arrange
        self.controller.player = None
        # Act
        self.controller.display_goodbye()
        # Assert
        self.mock_view.display_generic_goodbye.assert_called_once()

## --- INTEGRATED TESTS --- (TODO)
# 1. run_game

class TestRunGame(TestGameControllerBase):
    """Tests for the run_game() method and gameplay loop."""
    
    def test_run_game_happy_path(self):
        """"""
        # ... your test logic for this scenario ...
        pass
    
    # 2. edge case (out of chances): tests a turn where the player has 1 chance left, gives a wrong
    # answer, and asserts that the "out of chances" message is shown and the game loop terminates.
    def test_run_game_when_out_of_chances(self):
        """"""
    
    # change to run_game()
    # def test_handle_turn_with_wrong_answer_and_one_chance_left(self, mock_player, mock_question):
    #     """
    #     GIVEN a player and a question with a incorrect answer and one chance left 
    #     WHEN the controller handles the turn
    #     THEN the player's score is not increased, loses all chance, and correct feedback is given.
    #     """
    #     # Arrange
    #     self.controller.player = mock_player
    #     self.mock_view.get_player_answer.return_value = "Wrong Answer"
    #     mock_question.check_answer.return_value = False
    #     mock_question.correct_answer = "Correct Answer"
    #     # make sure only 1 chance is left
    #     for _ in range(self.controller.player.chances_left-1):
    #         self.controller.player.lose_chance()

    #     # Act
    #     self.controller._handle_turn(mock_question)

    #     # Assert
    #     self.mock_view.display_question.assert_called_once_with(mock_question)
    #     self.mock_view.get_player_answer.assert_called_once()
    #     mock_question.check_answer.assert_called_once_with("Wrong Answer")
    #     self.controller.player.add_score.assert_not_called()
    #     assert self.controller.player.lose_chance.call_count == 3
    #     self.mock_view.give_feedback.assert_called_once_with(False,
    #                                                          mock_question.correct_answer,
    #                                                          chances_left=self.controller.player.get_chances)   
        pass
    
    def test_run_game_when_user_quits_mid_game(self):
        """"""
        pass