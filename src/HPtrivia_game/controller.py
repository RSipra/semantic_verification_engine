'''
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

CLI MVP (core logic) -> game module (viewer and controller)

Currently both View and Controller are included in the same module for the MVP. 
Handled separately through classes. 

** Separation should be considered in next phase **
------------------------------------------------------------------

Game Logic for Trivia Game (CLI MVP): phase 1.2

 State 1. Initialize the game:
    - Load the dataset.
    - Load the trivia questions.
State 2. Introduction to the game and rules
    - Welcome the player.
    - Explain the rules of the game (allow to skip to player initialization in later versions )
    - Explain how to play 
    - Explain how to quit 
    - Explain the scoring system and chances. 
    - Ask for player name and house - Initialize the player.
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
    - "Thanks for playing!" End game
    
INCREMENTAL DEVELOPMENT:

Step 1: Core Loop: First, focus on getting the basic loop working in game.py. Make it load questions
via your Trivia class (once you add loading logic there), display them, get input, check the answer
using Question.check_answer, and keep a simple score variable (ignore Player/chances initially).
Make sure you can cycle through the questions.

Step 2: Integrate Player: Once the basic loop works, then add the code to ask for player name/house,
create the Player object, and modify the loop to update player.score instead of a simple variable.

Step 3: Add Chances: Once the Player is integrated, then add the chances_left logic 
(tracking, decrementing on incorrect answers, checking for game over).

Step 4: Add Intro & Levels: Finally, add the introductory explanation text and the end-game 
level display.
'''
import random
from pyfiglet import figlet_format  # to create ASCII art
from HPtrivia_game.player import Player
from HPtrivia_game.trivia import Trivia
from HPtrivia_game.constants import VALID_HOUSES, NUM_QUESTIONS_PER_SESSION

#-------------------------------------------------
# VIEW classes: handle game view and user input and output.    

class Introduction(Player):
    ''' Handles user interaction (View)'''
    
    @staticmethod
    def print_ascii_art(font_style: str = 'standard'):
        """
        Print the game title as ASCII art in the terminal using the pyfiglet package.

        This method is used in the CLI version of the game to display a stylized title.
        It uses the 'standard' font from pyfiglet by default. 
        The method takes an optional input for font as a string.

        References:
        - pyfiglet package: https://github.com/pwaller/pyfiglet
        - Font examples: http://www.figlet.org/examples.html
        """
        ## Can consider a random font selector for more fun later.
        game_title_text = "Harry Potter Trivia"
        # Try 'digital', 'ogre, 'gothic' or 'smscript' for a different vibe!
        print(figlet_format(text=game_title_text, font= font_style))  

    @ staticmethod
    def greet():
        """Return a warm and whimsical greeting to welcome the player to the game."""
        # can consider using the `shutil` package to dynamically adjust text to be centred in next phase
        return (
            "🧙‍♂️✨ Welcome, young wizard, to the world of magic! ✨⚡️\n"
            "🪄 You've entered the Harry Potter Trivia Challenge!\n"
            "Think you know the books inside and out? Let’s put your knowledge to the test! 📚🔮\n\n\n"
        )
        
    @ staticmethod
    def get_player_details():
        
        """
        Prompt the player for their name and house, and return a Player object.

        This method introduces the game with themed dialogue and allows the player
        to input their name and choose a Hogwarts house. A random house suggestion 
        is given by the Sorting Hat for flavor.

        Returns:
            Player: An instance of the Player class initialized with user inputs.
        """
        
        print("First, let's get to know you better!")
        
        # Obtain player name and validate name at input, loop until correct provided.
        
        # to make loop execution simpler for player can consider suggestion after ~3 tries
        # and provide "I pick?" option or end w. default name?
        while True:
            player_name = input("So what should I call you? Please enter your name: ").strip()
            if player_name:
                break
            print("Oops! Please enter a valid, non-empty name.")
        
        # Fun dialogue to keep the player engaged and link to theme -> sorting hat suggests a random house
        print("Hmmm, what would your house be....?\n\n")
        # could add a time delay here later.
        random_house = random.choice(VALID_HOUSES)
        print(f"The Sorting Hat thinks you *might* be a good fit for... {random_house.upper()}!\n\n 🎩")
        print("But you always get to choose!\n")
        
        # Player picks the hosue:
        while True:
            player_house = input("Which Hogwart's house has your allegiance?? \nEnter your house: ").strip().title()
            if player_house in VALID_HOUSES:
                break
            print(f"Uhoh! I didn't get that ... please enter a valid house from: {', '.join(VALID_HOUSES)}.")
            # can simplify later by breaking after ~3 incorrect answers and go with the random sorting house choice
            # will need to make the sorting house choice a variable then.
 
        # Initialize player
        player = Player(player_name, player_house)
        return player
    
    @staticmethod
    def explain_rules():
        ''' provide rules on how to play, chances, scoring.'''
    
    class GamePlayView:
        '''View methods during gameplay'''
    
    class GameEndView:
        '''View methods at the end of game play'''
    
    # ------------------------------------------------------------
    # CONTROLLER classes: manage flow between the game states.
    
    class GameController:
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
        def __init__(self): 
            self.player = None  # Instantiated by player during introduction
            self.trivia = Trivia()  # loads dataset + selects 10 questions
            self.current_question_index = 0
            self.game_over = False
        
        def start_game(self): # State 1
        # check inheritance from Trivia - and how it will be used. 
            """
            Initialize game by loading dataset and 10 random questions
            """
            
        def introduce_game(self): # State 2
            """
            setup the game introduction to run the Introduction class functions.
            """
            pass
        
        def run_game(self):  # State 3
            """
            Setup the game play logic / loop usingt use the GameView, Player, and Trivia classes. 
            run_game will be a wrapper with other internal private methods for individual jobs
            """
            # CHECK!
            # self._get_player_details()
            # Need to add chances_left here later!!
            while self.current_question_index != (NUM_QUESTIONS_PER_SESSION-1):
                self._play_round()
            self.end_game()
            
        # Private internal methods to perform individual jobs required for running the game 
        def _get_player_details(self):
            pass
            
        def _play_round(self):
            """
            One round of gameplay includes the following steps:

            1. Trivia provides a question
            2. View asks the question to the player
            3. Trivia checks the player's answer
            4. View displays feedback (correct/incorrect)
            5. Player score and state are updated
            6. Controller checks if the game should continue or end
            """
            pass
        
        def _update_game_state(self):
            pass
        
        def end_game(self):  # State 4
            """logic and view to end game, provide score, player level."""
            pass
