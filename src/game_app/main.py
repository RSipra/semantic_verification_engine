"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Main game entry point
"""
import logging
import time

# Import game modules:
from game_app.game_controller import GameController
from game_app.view import GameView
from game_app.warmup import build_next_session, orchestrate_game_session_warmup
from game_app.constants import (GameStatus, SessionStatus,
                                NUM_QUESTIONS_PER_SESSION as SESSION_SIZE)
from game_app.session_storage import save_performance_metrics, save_session_reports
from game_app.metrics_aggregator import aggregate_session_metrics, calculate_performance_metrics

# RANDOM_SEED = 26
RANDOM_SEED = None  # set to None for non-deterministic session allocation
SCOPE_ID="tracer_demo"

# TEMPORARILY MUTED FOR UI DEBUGGING

logging.disable(logging.CRITICAL)

# logging.basicConfig(
#     level=logging.INFO,  # change .DEBUG when troubleshooting.
#     format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

# Suppress noisy third-party libraries so they don't break the CLI UI
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

def main():
    """Sets up and runs the main application loop for the game."""
    
    # Let GoTTY and the browser negotiate screen size before initializing UI
    time.sleep(0.5)

    # 1. Initialize and setup the dependencies
    view = GameView()
    # log gameplay sessions only, not exhausted state
    all_session_reports = []
    all_session_aggregates = []
    
    # initialize controller with startup system signals
    controller = GameController(None, view)
    
    # 2. Run the one-time introduction to the game immediately as 
    #    as UX buffer for startup
    success = controller.start_game()
    
    if not success:
        return  # Exit if player setup fails or user quits

    # 3. load the waiting screen till startup finishes
    view.show_loading_screen()
    
    # 4. startup execution (currently blocking; future: async/background): 
    #    dataset hydration & validation, sbert + llm warmup
    #    Lazy load to reduce lag at immediate startup
    from engine.startup import orchestrate_application_startup 
    runtime_df, system_signals = orchestrate_application_startup()

    # session allocation logic (provides order list of dataset for building 
    # sequential session building within session object)
    session = orchestrate_game_session_warmup(runtime_df, RANDOM_SEED)

    # Update controller with startup system signals
    controller.system_startup_signals = system_signals

    # 5. Run question sessions until player quits or dataset exhausted.
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

        # data handling - logging and aggregation
        all_session_reports.append(session_report)
        session_aggregate = aggregate_session_metrics(session_report)
        all_session_aggregates.append(session_aggregate)

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

    # save session reports and aggregates to local dir in container    
    save_session_reports(category="reports", data=all_session_reports)
    save_session_reports(category="aggregates",data=all_session_aggregates)

    # generate and save perfromance metrics
    performance_metrics = calculate_performance_metrics(scope_id=SCOPE_ID,
                                                       session_aggregates=all_session_aggregates, 
                                                       scope="batch")
    save_performance_metrics(scope_id=SCOPE_ID,
                             metrics=performance_metrics,)

if __name__ == "__main__":
    main()
