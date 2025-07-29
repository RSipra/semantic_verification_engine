# Testing Introduction class - core logic MVP - manual testing.

from dotenv import load_dotenv
load_dotenv() 
from HPtrivia_game.game_controller import GameView as View
from HPtrivia_game.player import Player
import time

# Initialize
View = View()

# Full Introduction:
View.print_ascii_art(font_style='ogre')
View.print_dedication()
time.sleep(0.5)
View.print_greeting()
time.sleep(0.5)
player_name = View.get_player_name()
player_house = View.get_player_house()
test_player = Player(player_name, player_house)
View.print_personalized_player_welcome(test_player)
View.explain_gameplay(total_questions=10)

