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

STRUCTURE:

Structuring game.py:
To manage the state (like the current Player object, the Trivia session object, maybe the current
question index, game over status), it would be highly beneficial to create a GameController class 
within game.py.

* The __init__ could potentially load the data and set up the Trivia object.
* A run_game() method could contain the main logic (intro, loop, end game).
* Other methods could handle specific parts like _get_player_details(), _play_round(), 
  _display_results().

Learning Point: This practices OOP for managing application flow and state, rather than having lots
of loose variables and functions in your main script.

'''
