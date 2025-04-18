'''
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

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
# from HPtrivia_game.trivia import Trivia
from HPtrivia_game.constants import VALID_HOUSES, NUM_QUESTIONS_PER_SESSION

#-------------------------------------------------
# VIEW classes: handle game view and user input and output.

# START VIEW
class Introduction():
    ''' Handles user interaction (View) at the start of the game'''  
    def __init__(self):
        """
        Initialize the Introduction instance with game messages.

        The messages are stored in a dictionary for easy modification and later use.
        Each key corresponds to a section of the game intro (e.g., greeting, objective, etc.).
        """      
        # Message dictionary -  No commas in paranthesis for values = str otherwise tuple!
        self.messages = {
            "greeting": (
                "⚡️✨ Welcome, young withch or wizard, to the world of magic! ✨⚡️\n"
                "🪄 You've entered the Harry Potter Trivia Challenge!\n"
            ),
            "objective": (
                "You have been selected as a member of the house trivia team.\n"
                "Answer the trivia questions correctly and make your team proud! 🏅\n"
            ),
            "how_to_play": (
                "How to play the game:\n"
                f"- You will be given {NUM_QUESTIONS_PER_SESSION} random questions in this session.\n"
                "- Answer the questions with a short, clear, and concise sentence.\n"
                "- You will earn a point for every right answer.\n"
                "- Your final score will give determine your level of expertise!🤓\n"
                # can add explanations for chances_left and score later
            ),# can consider adding "Aveda Kedavara" as an easter egg for quitting? -> can also use if out of chances! create forbidden wrods list in constants.
            "how_to_quit": (
                "Quit mid-game:\n"
                "- You can quit anytime by typing 'quit' and pressing enter.\n"
                "- But keep in mind you will lose all game progress.\n"
            ),
            "start_game": (
                "🪄✨⚡️ Think you know the books inside and out?\n"
                "  📚🔮 Ready to test your magical knowledge?\n\n"
                "Grab your wand, summon your house pride, and let's begin! 🪄\n\n"
            ),
            "dedication": (
                "\n~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n"
                "\nDedicated to my daughter — the brightest witch of her age,\n"
                "the true Headmistress of Trivia, Minister of Fun, and Beta Tester Extraordinaire.\n"
                "This game was conjured with her magical energy, obscure knowledge, and relentless playtesting.\n\n"
                "May it bring *you*, dear player, just as much joy and adventure.\n\n"
                "Mischief managed... by us (R&Z)! ⚡️\n"
                "\n~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n\n"
            ),
            "tip": "💡Tip: Press Enter to move through each section as you learn how to play!"
            
        }
    # Add __str__ and __repr__
    
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
        print( '\n\n' + figlet_format(text=game_title_text, font= font_style) + '\n')  

    def greet(self):
        """
        Return a warm, whimsical greeting message for the player.

        This method retrieves the 'greeting' message from the messages dictionary.
        Future enhancements might add additional formatting or dynamic behavior.

        Returns:
            str: The greeting message.
        """
        # Can add extra behavior later (e.g. game quotes? more formatting? fun facts?)
        return self.messages["greeting"]
    
    def dedication(self):
        """
        Acknowledgements for game contributions :)
        This method retrieves the 'dedication' message from the messages dictionary.

        Returns:
            str: The greeting message.
        """
        return '\n' + self.messages["dedication"] + '\n'
        
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
            player_name = input("So what should I call you? Please enter your name: ").strip().title()
            if player_name:
                break
            print("Oops! Please enter a valid, non-empty name.")
        
        # Fun dialogue -> sorting hat suggests a random house
        print("\n\nHmmm, what would your house be....?\n\n")
        # could add a time delay here later.
        random_house = random.choice(VALID_HOUSES)
        print(f"The Sorting Hat thinks you *might* be a good fit for {random_house.upper()}!🎩\n\n ")
        print("But you always get to choose!\n")
        
        # Player picks the hosue:
        while True:
            player_house = \
            input("Which Hogwart's house has your allegiance?\nEnter your house: ").strip().title()
            if player_house in VALID_HOUSES:
                break
            print(f"Uhoh! I didn't get that ... please enter a valid house from: {', '.join(VALID_HOUSES)}.")
            # can simplify later by breaking after ~3 incorrect answers and go with the random sorting house choice
            # will need to make the sorting house choice a variable then.

        # Initialize player
        player = Player(player_name, player_house)
         # Can be replaced with function to print in color later?
        print("\n---------------------------------------------------------")
        print(f"\n\nWelcome to House {player_house}, {player_name}!\n\n")
        print("---------------------------------------------------------\n")
        
        return player
    
    def explain_gameplay(self):
        """
        Return the full explanation of the game’s rules and objectives.

        This method retrieves and concatenates the messages for objective, rules,
        quitting instructions, and the start prompt so that they can be printed together.

        Returns:
            str: A multiline string that explains gameplay instructions.
        """
        # Gather introduction messages in a sequence
        gameplay_sequence = [
            # Concatenate 'objective' and 'tip' -> run without input() break from the loop between the messages
            self.messages["objective"] + "\n" + self.messages["tip"], 
            self.messages["how_to_play"],
            self.messages["how_to_quit"],
            # self.messages["dedication"], # incase decide to run dedication here 
            self.messages["start_game"]
        ]
        for message in gameplay_sequence:
            print(message)
            input()
       
# GAMEPLAY VIEW:
class GamePlayView:
    '''View methods during gameplay'''
# END VIEW:  
class GameEndView:
    '''View methods at the end of game play'''
    
# ----------------------------------------------------------------------------------------------------------
    
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
        #self.trivia = Trivia()  # loads dataset + selects 10 questions
        self.current_question_index = 0
        self.game_over = False
    
    def start_game(self): # State 1
    # check inheritance from Trivia - and how it will be used. 
        """
        Initialize game by loading dataset and preselected number of random questions
        
        """
        
    def introduce_game(self): # State 2
        """
        setup the game introduction to run the Introduction class functions.
        """
    
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
    
    def _update_game_state(self):
        pass
    
    def end_game(self):  # State 4
        """logic and view to end game, provide score, player level."""
