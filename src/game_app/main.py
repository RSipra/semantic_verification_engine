"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Main game entry point
"""
import logging

# Import game modules:
from game_app.game_controller import GameController
from game_app.view import GameView
from game_app.warmup import build_next_session, orchestrate_game_session_warmup
from game_app.constants import (GameStatus, SessionStatus,
                                NUM_QUESTIONS_PER_SESSION as SESSION_SIZE)
from game_app.session_storage import save_session_reports
from engine.startup import orchestrate_application_startup

RANDOM_SEED = 26

logging.basicConfig(
    level=logging.INFO,  # change .DEBUG when troubleshooting.
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


def main():
    """Sets up and runs the main application loop for the game."""

    # 1. Initialize and setup the dependencies
    view = GameView()
    # log gameplay sessions only, not exhausted state
    all_session_reports = []

    # dataset hydration & validation, sbert + llm warmup
    runtime_df, system_signals = orchestrate_application_startup()

    # session allocation logic (provides order list of dataset for building 
    # sequential session building within session object)
    session = orchestrate_game_session_warmup(runtime_df, RANDOM_SEED)

    # initialize controller with startup system signals
    controller = GameController(system_signals, view)

    # 2. Run the one-time introduction to the game
    success = controller.start_game()
    if not success:
        return  # Exit if player setup fails or user quits

    # 3. Run question sessions until player quits or dataset exhausted.
    while True:
        # create new session
        session = build_next_session(session, runtime_df, SESSION_SIZE)

        #  pre-game exit (no session)
        if session.session_status == SessionStatus.EXHAUSTED:
            view.display_session_exhausted_goodbye()
            # not logging natural end.
            break

        # gameplay
        session_report = controller.run_game(session)
        all_session_reports.append(session_report)

        # End game if player wants to quit, dataset exhausted, or an error.
        if session_report.game_status in {GameStatus.QUIT,
                                          GameStatus.FAILED}:
            controller.display_goodbye(session_report)
            break

        # if status completed or lost - ask if they want to play again
        replay_status = view.ask_game_renew()

        if not replay_status:
            controller.display_goodbye(session_report)
            break

    # save session reports to local dir in container    
    save_session_reports(all_session_reports)
        
if __name__ == "__main__":
    main()
