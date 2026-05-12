from dotenv import load_dotenv
load_dotenv() 
from game_app.game_controller import GameView as View
from game_app.game_controller import GameController as Control
from game_app.trivia_manager import Trivia 
import game_app.constants as constants
from game_app.player import Player
import time

# 1. Define JUST the filename
csv_name = constants.MVP_TRIVIA_CSV_NAME
total_questons = 10

# 2. Initialize Trivia with the filename
trivia_session =Trivia(csv_name)

# game play: