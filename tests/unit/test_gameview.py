"""
Unit tests for the GameView class and its methods in the HPtrivia_game package.
"""
# pylint: disable=redefined-outer-name, protected-access
# from unittest.mock import patch
import time
import random
import io
from unittest.mock import patch
import pytest
from rich.panel import Panel
from rich.align import Align
from rich.console import Console
from HPtrivia_game.game_controller import GameView
from HPtrivia_game.player import Player
import HPtrivia_game.constants as const

# NOTE on testing:
# ------------------
# Since almost all methods are player-facing, they need to be tested.
# Using pytest built-in methods:
#    - monkeypatch -> sed to temporarily replace methods that bring input or externalities (like random numbers, 
#          file access, or the current time) to the method being tested. It's automatically torn down after the test.
#    - capsys -> Captures what is printed to the console (stdout and stderr) so it can be checked in an assert statement.

# TODO: Refactor tests to use io.StringIO for future robustness.
# -------------------
# Although `capsys` is currently working for all tests, its interaction with
# the `rich` library can be unpredictable. This is ok for the MVP.
# The recommended, most reliable pattern for capturing `rich.console.Console` output
# is to redirect it to an io.StringIO buffer. This will prevent potential intermittent
# test failures in the future.

## --- FIXTURES ---

@pytest.fixture
def gryffindor_player():
    """
    A fixture that creates and returns a sample Player instance
    """
    player = Player(name='Hermione', hogwarts_house=const.House.GRYFFINDOR)
    return player

@pytest.fixture
def slytherin_player():
    """
    A fixture that creates and returns a sample Player instance
    """
    player = Player(name='Draco', hogwarts_house=const.House.SLYTHERIN)
    return player

## --- UNIT TESTS ---

## --- Smart methods ---
# methods with logic, formatting, and conditional branches -> use capsys

# give_feedback - Happy path (answer is correct)
def test_give_feedback_when_answer_correct(monkeypatch, capsys):
    """
    GIVEN The player answer is correct
    WHEN give_feedback is called
    THEN it will return a correct answer feedback to the player
    """
    # Arrange
    view = GameView()
    feedback = "✅ Snape: You finally got it."
    # monkey patch: random feedback
    monkeypatch.setattr(random, 'choice', lambda _: feedback)
    # Act
    view.give_feedback(is_correct=True, correct_answer="any string", chances_left=3 ) # type: ignore
    # Assert
    captured = capsys.readouterr()
    expected_feedback = "✅ Snape: You finally got it."
    assert expected_feedback in captured.out

# give_feedback - unhappy path (answer is incorrect, chance >1)
def test_give_feedback_when_answer_incorrect_and_chances_left(monkeypatch, capsys):
    """
    GIVEN The player answer is incorrect and the player has more than 1 chance left
    WHEN give_feedback is called
    THEN it will return a correct answer with feedback that answer is incorrect and the remaining 
         number of chances to the player
    """
    # Arrange
    view = GameView()
    feedback = "💥 Not quite..."
    # monkey patch: random feedback
    monkeypatch.setattr(random, 'choice', lambda _: feedback)
    # Act
    view.give_feedback(is_correct=False, correct_answer="any string", chances_left=2 ) # type: ignore
    # Assert
    captured = capsys.readouterr()
    expected_feedback = "💥 Not quite..."
    assert expected_feedback in captured.out
    assert "any string" in captured.out 
    assert "Be careful! You have 2 chances remaining." in captured.out
    
# give_feedback - unhappy path (answer is incorrect, chance = 1)
def test_give_feedback_when_answer_incorrect_and_no_chances_left(monkeypatch, capsys):
    """
    GIVEN The player answer is incorrect and the player has only 1 chance left
    WHEN give_feedback is called
    THEN it will return a correct answer with feedback that answer is incorrect and warning
         that they only one chance left to the player
    """
    # Arrange
    view = GameView()
    feedback = "💥 Not quite..."
    # monkey patch: random feedback
    monkeypatch.setattr(random, 'choice', lambda _: feedback)
    # Act
    view.give_feedback(is_correct=False, correct_answer="any string", chances_left=1 ) # type: ignore
    # Assert
    captured = capsys.readouterr()
    expected_feedback = "💥 Not quite..."
    assert expected_feedback in captured.out
    assert "any string" in captured.out 
    assert "Watch out, you have one chance left!" in captured.out    

# display_player_rank -> HAPPY path 
def test_display_player_rank_happy_path(monkeypatch, slytherin_player, capsys):
    """
    GIVEN player and their rank
    WHEN display_player_rank is called
    THEN the correct formatted string with roast will be returned
    """
    # Arrange
    view=GameView()
    valid_rank = const.Rank.ENTHUSIAST
    roast = "🪄 You’ve got main character energy... just not on this chapter."
    # monkeypatch for random selection of roast from FEEDBACK
    monkeypatch.setattr(view, 'get_random_feedback_from_key', lambda *args, **kwargs: roast)  #handle the two positional arguments (roast_dict, rank) and the one keyword argument (default).
    # monkeypatch for time.sleep() - change to 0 or None to ignore it here
    monkeypatch.setattr(time, 'sleep', lambda _: None)

    # Act
    view.display_player_rank(valid_rank, slytherin_player)

    #Assert 
    captured = capsys.readouterr()
    expected_string1 = "you have attained the rank of"
    expected_string2 = "..."
    assert slytherin_player.name in captured.out
    assert expected_string1 in captured.out
    assert expected_string2 in captured.out
    assert roast in captured.out

# display_player_rank -> UNHAPPY path: invalid rank
def test_display_player_rank_unhappy_path(monkeypatch, slytherin_player, capsys):
    """
    GIVEN player and their rank
    WHEN display_player_rank is called
    THEN the correct formatted string with roast will be returned
    """
    # Arrange
    view=GameView()
    invalid_rank = const.Rank.UNKNOWN
    # monkeypatch for time.sleep() - change to 0 or None to ignore it here
    monkeypatch.setattr(time, 'sleep', lambda _: None)
    # Act
    view.display_player_rank(invalid_rank, slytherin_player)  #type: ignore
    #Assert 
    captured = capsys.readouterr()
    expected_string1 = 'Alright, Draco, you have attained the rank of "Unknown"!'
    expected_string2 = '...'
    expected_string3 = "unknown... hmmm, you could be a squib?"
    assert expected_string1 in captured.out
    assert expected_string2 in captured.out
    assert expected_string3 in captured.out

# house_head_reaction: HAPPY path (template can be created - ie rank exists)
def test_house_head_reaction_for_rank(gryffindor_player, capsys):
    """
    GIVEN player final rank and house
    WHEN house_head_reaction is called
    THEN it should print the correctly formatted message from the house head.
    """
    # Arrange
    view = GameView()
    rank = const.Rank.MASTER
    # Act
    view.house_head_reaction(rank, gryffindor_player)
    # Assert
    expected_househead = "Professor McGonagall"
    expected_house = "Gryffindor"
    expected_string = " beams with pride. 'Outstanding! You’ve done"
    captured = capsys.readouterr()
    assert expected_househead in captured.out
    assert expected_string in captured.out
    assert expected_house in captured.out
    
# house_head_reaction: UNHAPPY path (template canNOT be created - ie rank doesn't exists)
def test_house_head_reaction_for_invalid_rank(gryffindor_player, capsys):
    """
    GIVEN player incorrect final rank and correct house
    WHEN house_head_reaction is called
    THEN it should NOT print the formatted message from the house head.
    """
    # Arrange
    view = GameView()
    invalid_rank = "loser"
    # Act
    view.house_head_reaction(invalid_rank, gryffindor_player)  # type: ignore
    # Assert
    expected_househead = "Professor McGonagall"
    captured = capsys.readouterr()
    assert expected_househead not in captured.out
    assert captured.out.strip() == ""

# display_final_score - Happy path (questions >0, score displayed)
def test_display_final_score_with_questions(capsys):
    """
    GIVEN a score and a total number of questions > 0
    WHEN display_final_score is called
    THEN it should print the score, total, and formatted percentage
    """
    # Arrange
    view = GameView()
    score = 8
    total_questions = 10
    # Act
    view.display_final_score(score,total_questions)
    # Assert
    captured = capsys.readouterr()
    assert "You scored: 8 / 10 (80.0%)!!" in captured.out

# display_final_score - Unhappy path (questions = 0, score not displayed)
def test_display_final_score_with_zero_questions(capsys):
    """
    GIVEN a score and a total number of questions = 0
    WHEN display_final_score is called
    THEN it should print NOT print percentage to avoid ZeroDiv error
    """
    # Arrange
    view = GameView()
    score = 8
    total_questions = 0
    # Act
    view.display_final_score(score,total_questions)
    # Assert
    captured = capsys.readouterr()
    assert "---- Final Score ----" in captured.out
    assert "You scored:" not in captured.out
    
# display_final_housepoints: Happy path (player has a score)
def test_final_housepoints_with_score(slytherin_player, capsys):
    """
    GIVEN a score and player
    WHEN display_final_housepoints is called
    THEN it should print points awarded and name of player's house
    """
    #Arrange
    view = GameView()
    score = 8
    for _ in range(1,score+1):
        slytherin_player.add_score()

    # Act
    view.display_final_housepoints(slytherin_player.score, slytherin_player)
    # Assert
    captured = capsys.readouterr()
    expected_text = "8 points for Slytherin!!"
    assert expected_text in captured.out

# display_final_housepoints: Unhappy path (player has no score)
def test_final_housepoints_when_no_score(slytherin_player, capsys):
    """
    GIVEN zero score and a player
    WHEN display_final_housepoints is called
    THEN it should NOT print points awarded and name of player's house
    """
    #Arrange
    view = GameView()
    # Act
    view.display_final_housepoints(slytherin_player.score, slytherin_player)
    # Assert
    captured = capsys.readouterr()
    expected_text = "points for Slytherin!!"
    assert expected_text not in captured.out

## --- input methods ---
## INTRO view: check Happy vs. Unhappy path: use monkeypatch for user input

# get_player_name -> Happy path
def test_get_player_name_that_is_valid(monkeypatch, capsys):
    """
    GIVEN A player provides a valide name
    WHEN get_player_name is called
    THEN a confirmation greeting is printed with the player name
    """
    # Arrange
    view = GameView()
    test_name = 'Otto'
    monkeypatch.setattr('builtins.input', lambda: test_name)
    monkeypatch.setattr(time, 'sleep', lambda _:None)
    # Act
    player_name = view.get_player_name()
    captured = capsys.readouterr()    
    # Assert
    assert player_name == test_name
    assert "First, let's get to know you better!" in captured.out
    assert "Nice to meet you, Otto!!" in captured.out

# get_player_name -> unhappy path
def test_get_player_name_that_is_invalid(monkeypatch, capsys):
    """
    GIVEN A player provides no name
    WHEN get_player_name is called
    THEN an error message is printed till a valid one is provided
    """
    # Arrange
    view = GameView()
    inputs =['', '     ',  'Otto']
    monkeypatch.setattr('builtins.input', lambda: inputs.pop(0))
    monkeypatch.setattr(time, 'sleep', lambda _:None)
    # Act
    player_name = view.get_player_name()
    captured = capsys.readouterr()    
    # Assert
    assert player_name == "Otto"
    assert "Oops! Please enter a valid, non-empty name." in captured.out

# get_player_house -> Happy path (player picks their own house)
def test_get_player_house_of_choice(monkeypatch, capsys):
    """
    GIVEN: A player rejects proposed house and chooses own
    WHEN: get_player_house is called
    THEN: Then player's choice is assigned as their house
    """
    #Arrange
    view = GameView()
    random_substitute_house = const.House.RAVENCLAW
    player_choice_str = "Slytherin"
    expected_house_enum = const.House.SLYTHERIN

    monkeypatch.setattr(random, 'choice', lambda _: random_substitute_house)
    monkeypatch.setattr(time, 'sleep', lambda _: None)
    monkeypatch.setattr(view.console, 'input', lambda _: player_choice_str)  #using rich library input method direcly like in orignal method
    # Act
    returned_house = view.get_player_house()
    captured = capsys.readouterr()
    # Assert
    assert "Hmmm, what would your house be" in captured.out
    assert "The Sorting Hat thinks you *might* be a good fit for" in captured.out
    assert "RAVENCLAW" in captured.out
    assert returned_house == expected_house_enum
    
    # get_player_house -> Happy path (player keeps random choice)
def test_get_player_house_randomly_picked(monkeypatch, capsys):
    """
    GIVEN: A player accepts proposed randomly selected house
    WHEN: get_player_house is called
    THEN: Then random choice is assigned as the player's house
    """
    #Arrange
    view = GameView()
    random_substitute_house = const.House.RAVENCLAW
    player_choice_str = ""

    monkeypatch.setattr(random, 'choice', lambda _: random_substitute_house)
    monkeypatch.setattr(time, 'sleep', lambda _: None)
    monkeypatch.setattr(view.console, 'input', lambda _: player_choice_str)  #using rich library input method direcly like in orignal method
    # Act
    returned_house = view.get_player_house()
    captured = capsys.readouterr()
    # Assert
    assert "Hmmm, what would your house be" in captured.out
    assert "The Sorting Hat thinks you *might* be a good fit for" in captured.out
    assert "RAVENCLAW" in captured.out
    assert returned_house == random_substitute_house

# get_player_house -> unhappy path (player enters invalid choice)
def test_get_player_house_invalid_house(monkeypatch, capsys):
    """
    GIVEN: A player enters an invalid house, then a valid one.
    WHEN: get_player_house is called.
    THEN: It prints an error and returns the final, valid choice.
    """
    #Arrange
    view = GameView()
    random_substitute_house = const.House.RAVENCLAW
    player_inputs = ["Pumpernickle", "Hufflepuff"]

    monkeypatch.setattr(random, 'choice', lambda _: random_substitute_house)
    monkeypatch.setattr(time, 'sleep', lambda _: None)
    monkeypatch.setattr(view.console, 'input', lambda _: player_inputs.pop(0))  #using rich library input method direcly like in orignal method
    # Act
    returned_house = view.get_player_house()
    captured = capsys.readouterr()
    # Assert
    assert "Hmmm, what would your house be" in captured.out
    assert "The Sorting Hat thinks you *might* be a good fit for" in captured.out
    assert "RAVENCLAW" in captured.out
    assert "Uhoh! Please enter a valid house from" in captured.out
    assert returned_house == const.House.HUFFLEPUFF
    
## PLAY view
# get_player_answer
def test_get_player_answer_returns_stripped_input(monkeypatch):
    """
    GIVEN a user input with leading/trailing whitespace
    WHEN get_player_answer is called
    THEN it should return the stripped version of that input
    """
    # Arrange
    view = GameView()
    user_input="    Wingardium Leviosa  "  
    # Monkeypatch: use a private helper name code to simulate the user typing answer.
    monkeypatch.setattr(view, '_get_user_input', lambda _: user_input)
    # Act
    returned_answer = view.get_player_answer()
    # Assert
    assert returned_answer == "Wingardium Leviosa"

## QUIT view

# _get_user_input -> Happy path (player provides answer)
def test_get_user_input_returns_response(monkeypatch):
    """
    GIVEN a user provides input
    WHEN _get_user_input is called
    THEN it should return the provided input string.
    """
    # Arrange
    view = GameView()
    player_response= 'Harry Potter'
    monkeypatch.setattr(view.console,'input', lambda _: player_response)
    
    # Act
    returned_value= view._get_user_input("any prompt")
    # Assert
    assert returned_value == player_response

# _get_user_input -> Unhappy path (player enters quit)
def test_get_user_input_when_quitting(monkeypatch):
    """
    GIVEN the player enters 'quit' after prompt
    WHEN _get_user_input is called
    THEN it raises exception that user wants to quit.
    """
    # Arrange
    view = GameView()
    player_response= 'QuIt.  '
    monkeypatch.setattr(view.console,'input', lambda _: player_response)

    # Act and Assert
    with pytest.raises(const.UserWantsToQuit):
        view._get_user_input("Any prompt")

# prompt_to_save_report (happy path - player does NOT want to save a report)
def test_prompt_to_save_report_user_says_no(monkeypatch):
    """
    GIVEN the player enters "No" 
    WHEN prompted by prompt_to_save_report() to save session data in case they spotted an error
    THEN return False
    """
    # Arrange
    view = GameView()
    player_input = 'Nooooooo!'
    monkeypatch.setattr(view.console, 'input', lambda _:player_input)
    #Act
    reply_bool = view.prompt_to_save_report()

    #Assert
    assert reply_bool is False

# prompt_to_save_report (happy path - player does NOT want to save a report)
def test_prompt_to_save_report_user_says_yes(capsys, monkeypatch):
    """
    GIVEN the player enters "Yes" 
    WHEN prompted by prompt_to_save_report() to save session data in case they spotted an error
    THEN return False
    """
    # Arrange
    view = GameView()
    player_input = 'Yes ! '
    monkeypatch.setattr(view.console, 'input', lambda _:player_input)
    #Act
    reply_bool = view.prompt_to_save_report()
    captured = capsys.readouterr()

    #Assert
    assert reply_bool is True 
    assert "Saving session report..." in captured.out

# ask_game_renew -> happy path, user says yes
def test_ask_game_renew_player_says_yes(capsys, monkeypatch):
    """
    GIVEN the player types 'yes'
    WHEN ask_game_renew prompts the player for another round
    THEN returns True.
    """
    # Arrange
    view = GameView()
    player_response= 'Yes'
    monkeypatch.setattr(view.console, 'input', lambda _: player_response)
    expected_outcome = True
    # Act
    test_outcome = view.ask_game_renew()
    captured = capsys.readouterr()
    # Assert
    assert test_outcome == expected_outcome
    assert "Excellent! Preparing a new set of questions..." in captured.out

# ask_game_renew -> happy path, user says no
def test_ask_game_renew_player_says_no(monkeypatch):
    """
    GIVEN the player types 'no'
    WHEN ask_game_renew prompts the player for another round
    THEN returns False.
    """
   # Arrange
    view = GameView()
    player_response= 'No'
    monkeypatch.setattr(view.console, 'input', lambda _: player_response)
    expected_outcome = False
    # Act
    test_outcome = view.ask_game_renew()
    # Assert
    assert test_outcome == expected_outcome
    
# ask_game_renew -> unhappy path, user enters an invalid response and then 'y'
def test_ask_game_renew_player_input_invalide_then_yes(capsys, monkeypatch):
    """
    GIVEN the player types an invalid response ('maybe') and then 'yes'
    WHEN ask_game_renew prompts the player for another round
    THEN returns True.
    """
    # Arrange
    view = GameView()
    inputs = ['maybe', 'y']
    monkeypatch.setattr(view.console, 'input', lambda _: inputs.pop(0))
    # Act
    test_outcome = view.ask_game_renew()
    captured = capsys.readouterr()
    # Assert
    assert "Sorry, I didn't get that. Please enter 'y' or 'n'." in captured.out
    assert test_outcome is True
    
# ask_game_renew -> failure path, three invalid entries
def test_ask_game_renew_player_inputs_all_invalid(capsys, monkeypatch):
    """
    GIVEN the player types an invalid response ('maybe') three times
    WHEN ask_game_renew prompts the player for another round
    THEN returns False
    """
    # Arrange
    view = GameView()
    inputs = ['maybe', 'what','']
    monkeypatch.setattr(view.console, 'input', lambda _: inputs.pop(0))
    # Act
    test_outcome = view.ask_game_renew()
    captured = capsys.readouterr()
    # Assert
    assert "Sorry, I didn't get that. Please enter 'y' or 'n'." in captured.out
    assert "Too many invalid entries. Ending the game. Mischief managed!" in captured.out
    assert test_outcome is False

## --- Simple static view & view helpers ---
## INTRO view

# display_error
def test_dislay_error_prints_message(capsys):
    """
    GIVEN an error message
    WHEN display_error is called
    THEN it message should be formatted as an error and print it to the console
    """
    # Arrange
    view = GameView()
    error_message = "Any string"
    # Act
    view.display_error(error_message)
    captured = capsys.readouterr()
    # Assert
    assert error_message in captured.out

# _create_centered_panel
def test_to_create_centred_panel_from_text():
    """
    GIVEN content, a style, and a title
    WHEN _create_centered_panel is called
    THEN it should return a Panel object with the correct properties.
    """
    # Arrange
    view = GameView()
    test_content = "Test text"
    test_title = "TEST"
    test_style = 'bold green'
    # Act
    result_panel = view._create_centered_panel(
        content = test_content,
        style = test_style,
        title = test_title
    )
    # Assert
    assert isinstance(result_panel, Panel)
    # check simple attributes
    assert result_panel.border_style == test_style
    assert result_panel.title == f"[{test_style}]{test_title}[/]"
    assert result_panel.padding == (1, 2)
    # check nested content and its alignment
    assert isinstance(result_panel.renderable, Align)
    assert result_panel.renderable.align == "center"
    assert result_panel.renderable.renderable == test_content

# print_ascii_art (check text is in printed)
def test_print_ascii_art_prints_header():
    """
    GIVEN the font style
    WHEN print_ascii_art is called
    THEN it displays the game title as ASCII art, formatted correctly
    """
    # NOTE: StringIO is used here because ASCII art is printed with a rich 
    # console that can't be reliably tested with capsys - so using StringIO

    # Arrange
    view = GameView()
    test_font = 'ogre'
    # create an in-memory text buffer.
    string_io = io.StringIO()
    # tell the view's console to write to the buffer instead of the screen.
    view.console = Console(file=string_io)

    # Act
    view.print_ascii_art(font_style=test_font)
    captured_output = string_io.getvalue()

    # Assert
    assert "If cleverness is what you seek" in captured_output

# print_ascii_art (check internal logic by mocking pyfiglet call)
@patch('HPtrivia_game.game_controller.figlet_format')
def test_print_ascii_art_calls_figlet_correctly(mock_figlet):
    """
    GIVEN a specific font style
    WHEN print_ascii_art is called
    THEN it should call the pyfiglet.figlet_format function with the correct arguments.
    """
    # Arrange
    view = GameView()
    test_font = 'ogre'
    mock_figlet.return_value = "mocked art"
    string_io = io.StringIO()
    view.console = Console(file=string_io)
    
    # Act
    view.print_ascii_art(font_style=test_font)
    captured_output = string_io.getvalue()

    #Assert
    # Assert that the mocked function was called once with these exact arguments.
    mock_figlet.assert_called_once_with(
        text="Harry Potter Trivia", 
        font=test_font
    )
    # Assert that the mocked return value was printed.
    assert "mocked art" in captured_output

# print_dedication

# print_greeting
def test_print_greeting_displays_welcome_message(capsys):
    """
    GIVEN a GameView instance
    WHEN the print_greeting method is called
    THEN the correct welcome message should be printed to the console
    """
    # Arrange
    view = GameView()
    # Act
    view.print_greeting()
    # Assert
    captured = capsys.readouterr()  # Capture the printed output
    expected_text = "Welcome, young withch or wizard"
    assert expected_text in captured.out
    
# print_personalized_player_welcome
def test_print_personalized_welcome_for_player(gryffindor_player, capsys):
    """
    GIVEN a Player object created by a fixture
    WHEN print_personalized_player_welcome is called
    THEN it should display a welcome message with the player's name and house
    """
    # Arrange
    view = GameView()
    # Act
    view.print_personalized_player_welcome(gryffindor_player)
    # Assert
    captured = capsys.readouterr()
    expected_text = "Welcome to House"
    assert expected_text in captured.out
    assert "Gryffindor" in captured.out
    assert "Hermione" in captured.out

# explain_gameplay

## PLAY view
# display_question

## END view
# display_game_over
# get_random_feedback_from_key
# display_goodbye
# display_generic_goodbye

## QUIT view
# display_quit_message