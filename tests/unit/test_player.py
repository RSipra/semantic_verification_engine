"""Unit tests for the Player class in the HPtrivia_game module."""

import pytest
from game_app.player import Player
from game_app.constants import House
import game_app.constants as const
# pylint: disable=redefined-outer-name

@pytest.fixture
def default_player() -> Player:
    """A fixture that provides a standard Player instance for tests."""
    return Player(name="Hermione Granger", hogwarts_house=House.GRYFFINDOR)

def test_player_initialization(default_player: Player):
    """Tests that a Player object is created with the correct initial state."""
    assert default_player.score == 0
    assert default_player.get_chances == const.PLAYER_CHANCES # Check that chances are positive
    
def test_player_str(default_player: Player):
    """Tests the string representation of the Player object."""
    expected = (
        f"Player '{default_player.name}' is a member of House {default_player.house} "
        f"with a current score of {default_player.score}."
    )
    assert str(default_player) == expected
    
def test_player_repr(default_player: Player):
    """Tests the representation of the Player object."""
    player_repr = repr(default_player)
    expected = (
            f"Player("
            f"name='{default_player.name}', "
            f"hogwarts_house={repr(default_player.house)}, "
            f"score={default_player.score}, "
            f"chances_left={default_player.get_chances}"
            f")"
        )
    assert player_repr == expected

def test_player_equality_basic(default_player: Player):
    """
    Tests the fundamental equality cases: equality with an identical object,
    inequality with a different object, and inequality with other types.
    """
    same_player = Player(name="Hermione Granger", hogwarts_house=House.GRYFFINDOR)
    different_player = Player(name="Harry Potter", hogwarts_house=House.SLYTHERIN)
    
    assert default_player == same_player
    assert default_player != different_player
    assert default_player != "Not a Player"  #

def test_player_equality_on_attribute_change(default_player: Player):
    """
    Tests that equality is correctly False if only one key attribute is different.
    """
    # Test different name, same house
    player2 = Player("Ron Weasely", House.GRYFFINDOR)
    assert default_player != player2

    # Test same name, different house
    player3 = Player("Hermione Granger", House.SLYTHERIN)
    assert default_player != player3

def test_player_inequality_with_partial_name(default_player: Player):
    """
    Tests that players with partial or different full names are not equal.
    """
    player_first_name_only = Player(name="Hermione", hogwarts_house=const.House.GRYFFINDOR)
    assert default_player != player_first_name_only
    
def test_player_add_score(default_player: Player):
    """Tests that the add_score method correctly adds points to the player's score."""
    default_player.add_score()
    assert default_player.score == 1
    default_player.add_score()
    assert default_player.score == 2
    
def test_player_lose_chance(default_player: Player):
    """Tests that the lose_chance method correctly decrements chances."""
    # intial chances should be const.PLAYER_CHANCES
    initial_chances = const.PLAYER_CHANCES
    assert default_player.get_chances== initial_chances 
    # lose a chance
    default_player.lose_chance()
    assert default_player.get_chances == initial_chances - 1

def test_player_lose_all_chances(default_player: Player):
    """Tests that the player loses all chances when lose_chance is called repeatedly."""
    initial_chances = const.PLAYER_CHANCES
    for _ in range(initial_chances):
        default_player.lose_chance()
    assert default_player.get_chances == 0  # All chances should be lost
    
def test_player_chances_dont_go_negative(default_player: Player):
    """Tests that chances cannot go below zero."""
    chances_to_lose =  const.PLAYER_CHANCES + 1
    for _ in range(chances_to_lose):
        default_player.lose_chance()
    assert default_player.get_chances == 0
    
def test_reset_stats_from_mid_game(default_player: Player):
    """Tests that reset_stats works from a normal game state."""
    default_player.add_score()
    default_player.add_score()
    default_player.lose_chance()

    default_player.reset_stats()

    assert default_player.score == 0
    assert default_player.get_chances == const.PLAYER_CHANCES

def test_reset_stats_from_zero_chances(default_player: Player):
    """Tests that reset_stats restores chances from zero."""
    # Lose all chances
    for _ in range(const.PLAYER_CHANCES):
        default_player.lose_chance()
    # Sanity check that chances are zero
    assert default_player.has_chances_left() is False

    default_player.reset_stats()

    assert default_player.has_chances_left() is True
    assert default_player.get_chances == const.PLAYER_CHANCES

def test_has_chances_left_when_positive(default_player: Player):
    """Tests that has_chances_left is True when chances > 0."""
    # Player starts with 3 chances (or whatever the constant is)
    assert default_player.has_chances_left() is True

    default_player.lose_chance() # Chances are now 2
    assert default_player.has_chances_left() is True

def test_has_chances_left_when_zero(default_player: Player):
    """Tests that has_chances_left is False when chances are exactly 0."""
    for _ in range(const.PLAYER_CHANCES):
        default_player.lose_chance()

    assert default_player.get_chances == 0  # Confirm chances are 0
    assert default_player.has_chances_left() is False  
    
@pytest.mark.parametrize("score, total_questions, expected_rank", [
    (0, 10, const.Rank.NOVICE),      # 0% score -> NOVICE
    (3, 10, const.Rank.NOVICE),      # 30% score -> NOVICE
    (4, 10, const.Rank.ENTHUSIAST),  # 40% score -> ENTHUSIAST
    (6, 10, const.Rank.ENTHUSIAST),  # 60% score -> ENTHUSIAST
    (7, 10, const.Rank.EXPERT),      # 70% score -> EXPERT
    (8, 10, const.Rank.EXPERT),      # 80% score -> EXPERT
    (9, 10, const.Rank.MASTER),      # 90% score -> MASTER
    (10, 10, const.Rank.MASTER)      # 100% score -> MASTER
])

def test_get_rank_category_for_various_scores(default_player: Player,
                                              score: int, 
                                              total_questions: int, 
                                              expected_rank: const.Rank):
    """Tests that the rank calculation is correct for various scores."""
    # ARRANGE: Set the score on the player object for this specific test case
    default_player._score = score

    # ACT: Call the method with the total_questions for this case
    actual_rank = default_player.find_player_wizard_rank(total_questions=total_questions)

    # ASSERT: Check that the actual result matches the expected result for this case
    assert actual_rank == expected_rank

def test_get_rank_category_with_zero_questions(default_player: Player):
    """Tests the edge case where total_questions is zero."""
    # Test the specific guard clause at the top of your method
    assert default_player.find_player_wizard_rank(total_questions=0) == const.Rank.UNKNOWN
