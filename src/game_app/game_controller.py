'''
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Game Controller Module
-----------------------------------------------------------------------

Game orchestrator responsible for executing a single gameplay run for a
player, including introduction, session execution, and end-game flow.

Acts as the interface between:
- main application loop (multi-session orchestration)
- view layer (user interaction)
- evaluation router (tiered hybrid semantic / structured evaluation system)

Core responsibilities:
- Handle player introduction and initialization
- Execute a full game session via run_game(session)
- Manage per-turn execution via _handle_turn()
- Route answers through evaluation_router for structured evaluation
- Update player state based on evaluation results
- Aggregate turn-level results into SessionReport
- Coordinate end-of-session flow and exit messaging

Game flow (high-level):
1. Introduction and player setup
2. Session execution (question loop)
   - Display question
   - Collect input
   - Evaluate answer via routed evaluators
   - Update player state
   - Return TurnResult
3. Session finalization
   - Aggregate SessionReport
   - Handle quit / failure / completion states
   - Delegate persistence to main layer

TODO:
system_signals (from startup) reserved for future runtime UX handling
(e.g. degraded/free-tier latency warnings, temporary LLM disablement)    
'''
import time

from game_app.player import Player
from game_app.constants import NUM_QUESTIONS_PER_SESSION, GameStatus, UserWantsToQuit
from game_app.types import Question, SessionReport, Session
from engine.dto import TurnResult
from engine.evaluators.router import evaluation_router

## GAMEPLAY CONTROLLER: manage flow between the game states.

class GameController():
    """
    Main game controller for the Trivia game.
        - Manage the game flow and state. 
        - Interact with Player and Trivia modules.
        - To manage the state (like the current Player object, the Trivia session object, 
            maybe the current question index, game over status).
        - Other methods could handle specific parts like _get_player_details(), _play_round(), 
            _display_results().r adding a new player,
    """

    # Track current state of the game.
    def __init__(self, system_signals, view): 
        self.player = None  # set during introduction phase
        self.player_initialized = False  # flipped to True after Introduction. Player is invariant after that
        self.system_startup_signals = system_signals
        self.view = view  # Persistent component

## Game Introduction

    def _handle_introduction(self, total_questions: int):
        """
        Setup the game introduction to run the Introduction class functions.
        This will display:
        1. Game title with ASCII art
        2. Displays game dedication message
        3. Displays the player greetings
        4. Retrieves the player details and initializes the Player
        5. Explains the game play that leads to the start of the game.
    
        UX: Breaks the flow into distinct 'Screens'.
        """

        # --- SCREEN 1: THE HOOK (Title & Greeting) ---
        # 1. game title (view already clears the screen here)
        self.view.print_ascii_art(font_style='ogre')

        # 2. greeting 
        self.view.print_greeting()

        # 3. pause to let player read before next input
        self.view.console.print("\n[dim italic]Press Enter to enter the Great Hall...[/]\n")
        self.view.console.input()

        # --- SCREEN 2: IDENTITY (Name & House) ---
        self.view.console.clear() # wipe screen

        # 4. get name
        player_name = self.view.get_player_name()

        # 5. get house
        player_house = self.view.get_player_house(player_name)

        # create player object
        self.player = Player(player_name, player_house)

        # --- SCREEN 3: THE REVEAL (Welcome Panel) ---
        self.view.console.clear()  #wipe screen

        # 6. welcome panel
        self.view.print_personalized_player_welcome(self.player)

        # pause before next screen
        self.view.console.print("\n[dim italic]Press Enter to learn the rules...[/]")
        self.view.console.input()

        # --- SCREEN 4: THE RULES ---
        self.view.console.clear()  # clear screen

        # 7. explain game play 
        # (This method has its own pauses, so it works well on a fresh screen)
        self.view.explain_gameplay(total_questions)

        # final clear so the first question pops on a black background
        self.view.console.clear()

    def start_game(self) -> bool:
        """
        Handles the one-time player setup and introduction.
        This is so the introduction is only required once if the 
        player wants to play multiple rounds.
        Returns True if the setup was successful, False otherwise.
        """
        # configuration
        total_questions = NUM_QUESTIONS_PER_SESSION
        # interactive introduction
        self._handle_introduction(total_questions)
        assert self.player is not None, "Player must be set during initialization"
        self.player_initialized = True

        return True

## Run Sessions

    def run_game(self, session: Session) -> SessionReport:
        """
        Orchestrates a single, complete game session from introduction to end-game.

        This method is the main driver for a round of trivia. It calls internal
        helper methods to handle the player introduction, data setup, the
        turn-by-turn gameplay loop, and the final summary.

        At the conclusion of the session, it prompts the user if they wish to
        play again and communicates their choice via its return value.
        
        TODO: consolidate report building into a helper to avoid repetition

        Returns:
            session_report : returns status report for session action in Main.
        """

        # Guard clause: player initialized by controller at startup as invariant.
        if self.player is None:
            raise RuntimeError(
                "GameController state invalid: player not initialized before run_game()")
        # Guard clause: startup orchestration guarantees runtime question availability.
        if not session.questions:
            raise RuntimeError(
                "Session initialized without questions. "
                "Runtime invariant violated.")

        # initialize
        start_time = time.time()
        questions_answered = 0
        all_turn_results = []
        player = self.player

        session_report = SessionReport(
            game_id = session.game_id,
            total_questions = session.session_size,
            player_name = player.name,
            house = player.house
            )
        # Gameplay single session loop
        try:
            # Reset the player's stats for the new round before the questions begin.
            player.reset_stats()

            for question in session.questions:

                # single question presentation and evaluation
                turn_result = self._handle_turn(question)
                all_turn_results.append(turn_result)
                questions_answered +=1

                # game loss path
                if not player.has_chances_left():

                    # populate report
                    session_report.game_status = GameStatus.LOST
                    session_report.score = player.score
                    session_report.duration_sec = time.time() - start_time
                    session_report.questions_answered = questions_answered
                    session_report.all_turn_results = all_turn_results

                    # end game
                    self.view.display_error("Uh oh! You've run out of chances! 🥺")
                    self._render_session_summary(session_report)

                    return session_report

            # populate report
            session_report.game_status = GameStatus.COMPLETED
            session_report.score = player.score
            session_report.duration_sec = time.time() - start_time
            session_report.questions_answered = questions_answered
            session_report.all_turn_results = all_turn_results

            # game win: session completed
            self._render_session_summary(session_report)

            return session_report

        # custom exception to quit if player enters 'quit' at any input and end game.
        except UserWantsToQuit:
            session_report.game_status = GameStatus.QUIT
            session_report.duration_sec = time.time() - start_time
            session_report.score = None  # score ommited for quit in MVP
            session_report.questions_answered = questions_answered
            session_report.all_turn_results = all_turn_results

            return session_report

    # handle a single turn with the Question object
    def _handle_turn(self, question: Question) -> TurnResult:
        """
        Executes a single question turn.

        Flow:
        1. Display question to player via View
        2. Collect player input
        3. Route question + answer through evaluation_router
        4. Build TurnResult containing:
        - question metadata (id, type, answer type)
        - evaluation output
        5. Update Player state based on evaluation result
        6. Provide feedback via View
        7. Return TurnResult for session aggregation

        Returns:
            TurnResult: full record of the executed turn including evaluation outcome
        """
        assert self.player is not None
        player = self.player

        # 1. ask the question
        # UX: pass current score to the view for the header
        self.view.display_question(question, player.score)

        #2. get player's answer
        player_answer = self.view.get_player_answer()

        #3. check the answer & chances left
        result = evaluation_router(player_answer, question)

        # evaluation report for controller
        turn_report = TurnResult(
            question_id = question.master_id,
            question_type = question.question_type,
            answer_type = question.answer_type,
            evaluation = result
        )

        is_answer_correct = turn_report.evaluation.is_correct

        #4. update player score and state
        if is_answer_correct is True:
            player.add_score()
        else:
            player.lose_chance()

        #5. provide player feedback on answer
        self.view.give_feedback(is_answer_correct,
                                question.answer,
                                chances_left= player.get_chances)
        return turn_report

##  End Game

    # End game sequence
    def _render_session_summary(self, session_report: SessionReport) -> None: 
        """Orchestrates the session end sequence by calling the View."""

        assert self.player is not None, "Player must be set during initialization"

        total_questions = session_report.total_questions
        
        # 0. display game-over message
        self.view.display_game_over()

        # 1. get player final score and display it
        final_score = self.player.score
        self.view.display_final_score(final_score, total_questions)

        # 2. Get player rank and display rank and roast! :D
        final_rank = self.player.find_player_wizard_rank(total_questions)
        self.view.display_player_rank(final_rank, self.player)
        self.view.display_final_housepoints(final_score, self.player)

        return

    # wrapper for main to display final goodbye
    def display_goodbye(self, session_report: SessionReport):
        """
        Orchestrates the display of a final goodbye message to the player.

        This method is intended to be called by the main application runner
        after the primary game loop has exited. It routes exit messages
        based on session and game status.
        """

        player_name = session_report.player_name
        game_status = session_report.game_status

        match game_status:
            case GameStatus.COMPLETED | GameStatus.LOST:
                # customized message with player name
                self.view.display_goodbye(player_name)
            case GameStatus.FAILED:
            # A generic goodbye if there was no player
                self.view.display_generic_goodbye()
            case GameStatus.QUIT:
                self.view.display_quit_message()
        return
