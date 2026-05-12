''' 
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================
#
# =================================================================
# PHASE 1 STABLE VERSION - DO NOT REFACTOR IN THESE FILE
# -----------------------------------------------------------------
# This game version is synced to the Phase 1 GCP VM. 
# For Phase 2 (FastAPI/Serverless) development, 
# please work in the /HPtrivia_game_p2_refactor directory to avoid
# overwriting the live demo via the VS Code Remote portal.
# =================================================================
#
------------------------------------------------------------------
'''
# Import game modules:
from game_app.game_controller import GameController
from game_app.trivia_manager  import Trivia
from game_app.constants import MVP_TRIVIA_CSV_NAME


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
