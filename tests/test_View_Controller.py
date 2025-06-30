from dotenv import load_dotenv
load_dotenv() 
from HPtrivia_game.game_controller import GameView as View
from HPtrivia_game.game_controller import GameController as Control
from HPtrivia_game.trivia_manager import Trivia 
import HPtrivia_game.constants as constants
from HPtrivia_game.player import Player
import time

# 1. Define JUST the filename
csv_name = constants.MVP_TRIVIA_CSV_NAME
total_questons = 10

# 2. Initialize Trivia with the filename
trivia_session =Trivia(csv_name)

# game play: