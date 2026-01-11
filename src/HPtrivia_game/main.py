''' 
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

The runner module that executes the game.

------------------------------------------------------------------
'''
# Import game modules:
from HPtrivia_game.game_controller import GameController
from HPtrivia_game.trivia_manager  import Trivia
from HPtrivia_game.constants import MVP_TRIVIA_CSV_NAME


def main():
    """Sets up and runs the main application loop for the game."""
    # 1. setup the dependencies
    trivia_session = Trivia(MVP_TRIVIA_CSV_NAME)
    controller = GameController(trivia_session)
    # 2. Run the one-time introduction to the game
    if not controller.start_game():
        return # Exit if player setup fails or user quits
    # 3. Run question sessons until player quits
    while True:
        # Run one full session that returns bool to continue or not
        play_game_again = controller.run_game()
        # End game if player wants to quite
        if not play_game_again:
            break
    controller.display_goodbye()    
        
if __name__ == "__main__":
    main()
