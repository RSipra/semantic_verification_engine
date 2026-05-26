'''
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Game Controller Module
-----------------------------------------------------------------------

CLI MVP (core logic) -> game module (viewer and controller)

Currently both View and Controller are included in the same module for the MVP. 
Handled separately through classes. 

** Separation into separate VIEW and CONTROLLER modules will be considered in the next phase **
------------------------------------------------------------------

Game Logic for Trivia Game (CLI MVP): phase 1.2

State 1. Initialize the game:
    - Load the dataset.
    - Load the trivia questions.
State 2. Introduction to the game and rules
    - Title + brief acknowledgements  
    - Welcome the player.
    - Ask for player name and house - Initialize the player.
    - Explain the rules of the game (allow to skip to player initialization in later versions )
    - Explain how to play 
    - Explain how to quit 
    - Explain the scoring system and chances (* to be added in later)
State 3. Start the game loop:
    - Ask the player a question.
    - Get the player's answer. check if they entered quit (if quit chosen -> end game)
    - Check if the answer is correct and update score and chances left:
        - If player answer is correct: add 1 point to the score.
        - If player answer is incorrect:
            - Reduce the player's chances by 1. If no chances left, end the game.
    - load next question until end of trivia question set.
State 4. End the game:
    - Display the player's score and level.
    - "Thanks for playing!" End game or renew for another round.
    
'''

from datetime import datetime
from pathlib import Path
import json
from typing import List, Any, Dict#, Optional
from pyfiglet import figlet_format  # to create ASCII art
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.text import Text
from rich.align import Align 
from game_app.player import Player
from game_app.trivia_manager import Question
import game_app.constants as const
import game_app.utils_general as ut

#-----------------------------------------


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
    def __init__(self, trivia_session): 
        self.player = None  # Instantiated by player during introduction
        self.trivia_manager = trivia_session  # Trivia object from main; loads dataset + selects predefined num of questions
        self.current_question_index = 0
        self.current_score = 0
        self.game_over = False
        self.view = GameView()  # Persistent component  
        # print("DEBUG: GameController initialized.")
    
## CNTL: Initialization

    # Use trivia_manager to setup the questions for the session
    def _setup_session(self, total_questions: int): # State 1
        """Handles the entire data setup process for a new game session."""
        # print("Preparing your questions...")
        try:
            # Tell the trivia_manager to load the data
            self.trivia_manager.start(num_questions_to_load= total_questions)
            # Get the list of questions from the public getter method
            session_questions = self.trivia_manager.get_session_questions()
            # Return the list so run_game can use it
            return session_questions
        except Exception as e:
            self.view.display_error(f"Could not set up the trivia data. {e}")
            return None   
    
## CNTL: Introduction 

    def _handle_introduction(self, total_questions: int): # State 2
        """
        Setup the game introduction to run the Introduction class functions.
        This will display:
        1. Game title with ASCII art
        2. Displays game dedication message
        3. Displays the player greetings
        4. Retrieves the player details and initializes the Player
        5. Explains the game play that leads to the start of the game.
    
        Updated for Better UX: Breaks the flow into distinct 'Screens'.
        """
    
        # --- SCREEN 1: THE HOOK (Title & Greeting) ---
        # 1. Game title (Your view already clears the screen here)
        self.view.print_ascii_art(font_style='ogre')
        
        # 2. Greeting (Print it below the title)
        self.view.print_greeting()
        
        # 3. PAUSE: Let them read before rushing to input
        self.view.console.print("\n[dim italic]Press Enter to enter the Great Hall...[/]\n")
        self.view.console.input() 
        
        
        # --- SCREEN 2: IDENTITY (Name & House) ---
        self.view.console.clear() # <--- WIPE THE SLATE CLEAN
        
        # 4. Get Name
        player_name = self.view.get_player_name()
        
        # 5. Get House 
        # (We keep these on the same screen so it feels like filling out a form)
        player_house = self.view.get_player_house(player_name)
        
        # Create Player Object
        self.player = Player(player_name, player_house)
        
        
        # --- SCREEN 3: THE REVEAL (Welcome Panel) ---
        self.view.console.clear() # <--- WIPE AGAIN
        
        # 6. Big Welcome Panel
        self.view.print_personalized_player_welcome(self.player)
        
        # Pause to let them admire their house colors
        self.view.console.print("\n[dim italic]Press Enter to learn the rules...[/]")
        self.view.console.input()


        # --- SCREEN 4: THE RULES ---
        self.view.console.clear() # <--- WIPE AGAIN
        
        # 7. Explain game play 
        # (This method has its own pauses, so it works well on a fresh screen)
        self.view.explain_gameplay(total_questions)
        
        # Final clear so the first question pops on a black background
        self.view.console.clear()

    def start_game(self) -> bool:
        """
        Handles the one-time player setup and introduction.
        This is so the introduction is only required once if the 
        player wants to play multiple rounds.
        Returns True if the setup was successful, False otherwise.
        """
        # 0. Configuration
        total_questions = const.NUM_QUESTIONS_PER_SESSION
        # State 1: Introduction
        self._handle_introduction(total_questions)
        
        return self.player is not None

## CNTL: Run session     
    def run_game(self) -> bool:
        """
        Orchestrates a single, complete game session from introduction to end-game.

        This method is the main driver for a round of trivia. It calls internal
        helper methods to handle the player introduction, data setup, the
        turn-by-turn gameplay loop, and the final summary.

        At the conclusion of the session, it prompts the user if they wish to
        play again and communicates their choice via its return value.

        Returns:
            bool: `True` if the player chooses to play another round, otherwise
                  `False`. This value is intended to be used by the main
                   application loop in `main.py` to determine whether to
                   start a new game or exit the program.
        """
        try:
            # 0. Configuration
            total_questions = const.NUM_QUESTIONS_PER_SESSION
            
            # State 1: handled once only at start of game in main
            
            # Guard Clause: Check if player initialized successfully
            if not self.player:
                self.view.display_error("Cannot play a round without a player. Please start the game first.")
                return False # Exit the round gracefully

            # State 2: Data setup
            session_questions = self._setup_session(total_questions)
            # Guard Clause: Check if questions were loaded successfully
            if not session_questions:
                self.view.display_error("Could not load questions for the session.")
                return False

            # State 3: Gameplay loop
            # Reset the player's stats for the new round before the questions begin.
            self.player.reset_stats()

            for question in session_questions:
                self._handle_turn(question)
                # make sure they have chances left
                if not self.player.has_chances_left():
                    self.view.display_error("Uh oh! You've run out of chances! 🥺")
                    break

            # State 4: End game
            return self._end_game(total_questions) # returns bool to main.py (T: another round, F: quit)
        
        # custom exception to quit if player enters 'quit' at any input and end game.
        except const.UserWantsToQuit: 
            self.view.display_quit_message() 
            return False
    
    # Handle a single turn with the Question object     
    def _handle_turn(self, question: Question) -> None: # state 3
        """
        One round of gameplay includes the following steps:
        1. View asks the question to the player
        2. Views gets the player's answer and passes to the Controller
        3. Controller passes the player's answer through Question.check_answer(), method checks and provides boolean
        4. Controller passes boolean to View 
        5. View displays feedback (correct/incorrect)
        6. Player score and state are updated
        """
        if not self.player:
            self.view.display_error("Cannot handle turn because no player exists.")
            return 
        
        #1. Ask the question
        # ### UX IMPROVEMENT: Passing current score to the view for the header ###
        self.view.display_question(question, self.player.score)
        
        #2. Get the player's answer
        player_answer = self.view.get_player_answer()
        
        #3. Check the answer & chances left
        is_correct = question.check_answer(player_answer)
        
        #4. update player score and state
        if is_correct:
            self.player.add_score()
        else:
            self.player.lose_chance()
            
        #5. Provide player feedback on answer
        self.view.give_feedback(is_correct, 
                                question.correct_answer, 
                                chances_left= self.player.get_chances)

## CNTL: End session 
    
    # Generate trivia set report incase any errors are spotted in the dataset.
    def _save_session_report(self):
        """Gets session data from Trivia and saves it as a JSON report."""
        # 1. Get the data from the trivia manager
        report_data = self.trivia_manager.get_session_report_data()

        if not report_data:
            print("DEBUG: No questions in session, skipping report.")
            return

        # 2. Define a directory for reports and make sure it exists
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)

        # 3. Create a unique filename with a timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"trivia_session_{timestamp}.json"
        filepath = reports_dir / filename

        # 4. Write the data to a JSON file
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=4, ensure_ascii=False)
            print(f"DEBUG: Session report saved to {filepath}")
        except Exception as e:
            # Use the view to display the error to the user
            self.view.display_error(f"Could not save session report: {e}")
                
    # End game sequence    
    def _end_game(self, total_questions: int) -> bool:  # State 4
        """Orchestrates the entire end-game sequence by calling the View."""

        # Guard clause incase player was not instantiated in Introduction 
        if self.player is None:
            self.view.display_error("No player data available to show a final score.")
            # Since there's no player, we can't really ask them to play again.
            return False

        # 0. display game-over message
        self.view.display_game_over()

        # 1. get player final score and display it
        final_score = self.player.score
        self.view.display_final_score(final_score, total_questions)

        # 2. Get player rank and display rank and roast! :D
        final_rank = self.player.find_player_wizard_rank(total_questions)
        self.view.display_player_rank(final_rank, self.player)
        self.view.display_final_housepoints(final_score, self.player) 
        
        # 3. Ask the player if they want to save a report by calling the view.
        if self.view.prompt_to_save_report():
            # 2. If they say yes, then call the internal save method.
            self._save_session_report()
        
        # 4. Offer another round otherwise quit game
        continue_game = self.view.ask_game_renew()
        
        return continue_game
    
    # wrapper for main to display final goodbye
    def display_goodbye(self):
        """
        Orchestrates the display of a final goodbye message to the player.

        This method is intended to be called by the main application runner
        after the primary game loop has exited. It checks if a Player object
        was successfully created during the session.

        If a player exists, it delegates the task of printing a personalized
        goodbye message to the View. If no player was created (e.g., the
        user quit during the introduction), it handles a generic farewell.
        """
        if self.player:
            player_name = self.player.name
            self.view.display_goodbye(player_name)
        else:
            # A generic goodbye if there was no player
            self.view.display_generic_goodbye()