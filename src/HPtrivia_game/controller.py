# Main game logic

'''
Game Logic for Trivia Game (CLI MVP):

 1. Initialize the game:
    - Load the dataset.
    - Load the trivia questions.
2. Introduction to the game and rules
    - Welcome the player.
    - Explain the rules of the game (allow to skip to player initialization in later versions )
    - Explain how to play 
    - Explain how to quit 
    - Explain the scoring system and chances. 
    - Ask for player name and house - Initialize the player.
3. Start the game loop:
    - Ask the player a question.
    - Get the player's answer. check if they entered quit (if quit chosen -> end game)
    - Check if the answer is correct and update score and chances left:
        - If player answer is correct: add 1 point to the score.
        - If player answer is incorrect:
            - Reduce the player's chances by 1. If no chances left, end the game.
    - load next question until end of trivia question set.
4. End the game:
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

STRUCTURE: PHASE 1 (MVP)

Structuring game.py: Integrated  interface / view in game.py module- at a minimum:
1. CLIview class to handle user input and output.
2. GameController class to manage the game flow and state. Interact with Player and Trivia modules.
    - To manage the state (like the current Player object, the Trivia session object, 
      maybe the current question index, game over status).
        * The __init__ could potentially load the data and set up the Trivia object.
        * A run_game() method could contain the main logic (intro, loop, end game).
        * Other methods could handle specific parts like _get_player_details(), _play_round(), 
        _display_results().r adding a new player,

Learning Point: This practices OOP for managing application flow and state, rather than having lots
of loose variables and functions in your main script.

PHASE 2: consider a separate module for game logic and view especially if moving to a GUI or 
web app.

'''
from modules.player import Player
from modules.trivia import Trivia

''' 
Currently both View and Controller are included in the same module for the MVP. Handled separately through classes. 

-----
** Separation should be considered in next phase.

'''

#-------------------------------------------------
    
# VIEW classes    

class Start(Trivia):
    # check inheritance from Trivia - and how it will be used. 
    '''Initialize game by loading dataset and 10 random questions'''
    pass
    
class Introduction(Player):
    ''' Handles user interaction (View)'''
    
    @ staticmethod
    def greet():
        '''print message to welcome player and introduce game'''
        return "Welcome to the Harry Potter Trivia!🪄 \n You love the books but how well do you know them? Let's find out!!" 
    
    @staticmethod
    def get_player_details():
        
        ''' Get the player to input their username and hogwart's house and use it to initialize the player'''
        
        print("So, let's get to know you better!")
        # Validate name at input, loop until correct provided.
        while True:
            player_name = input("So what should I call you? Please enter your name: ").strip()
            if player_name:
                break
            print("Oops! Please enter a valid, non-empty name.")

        
        player_house = input("Which Hogwart's house has your allegiance?? \nEnter your house: ")
        # Validate house at input:
       
        
        # Initialize player
        player = Player(player_name, player_house)
        print('Thanks!')
        return player
    
    @staticmethod
    def explain_rules():
        ''' provide rules on how to play, chances, scoring.'''
        pass
    
    class GamePlayView:
        '''View methods during gameplay'''
        pass
    
    class GameEndView:
        '''View methods at the end of game play'''
        pass
    # ------------------------------------------------------------
    # CONTROLLER classes
    
    class GameController:
        """Main game controller for the Trivia game."""
    
    def __init__(self):
        # inherit from player / trivia
        pass
    
        
        
        
    
