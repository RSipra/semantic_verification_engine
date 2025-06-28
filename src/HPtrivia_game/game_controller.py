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
    - "Thanks for playing!" End game or renew for another round.
    
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
import time
from typing import List, Any, Dict, Optional
from pyfiglet import figlet_format  # to create ASCII art
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from HPtrivia_game.player import Player
from HPtrivia_game.trivia_manager import Question
import HPtrivia_game.constants as const

#-----------------------------------------
       
## GAMEPLAY VIEW MODULE
class GameView:
    """
    Handles all presentation (display) and user input for the trivia game.
    """
## VIEW class atrributes

    # 1.  Colour theme for the `rich` cli formatting package
    THEME = {
        "intro": "bold purple",
        "question_border": "dark_violet",
        "prompt": "magenta",
        "success": "bold green",
        "error": "bold red",
        "feedback": "yellow",
        "goodbye": "bold cyan"
    }

    # 2. Messages used in the various sections of the game introduction
   
    INTRO_MESSAGES = {
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
            "- You will be given {num_questions} random questions in this session.\n"
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
            "This game was conjured with her magical energy, obscure knowledge, and relentless play-testing.\n\n"
            "May it bring *you*, dear player, just as much joy and adventure!\n\n"
            "Mischief managed... by us (R & Z)! ⚡️\n"
            "\n~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~\n\n"
        ),
        "tip": "💡Tip: Press Enter to move through each section as you learn how to play!"
        
    }
    
    # Feedback when a player gets the answer correct (randomly chosen)
    CORRECT_ANS_FEEDBACK: List[str] = [
                "✅ Correct! ⚡️😁✨",
                "✅ Yup, that's it! 👏🏼",
                "✅ Awesome! are you trying to give Hermione a run for her money?",
                "✅ Yes, that's right! 👌🏼",
                "✅ Excellent! Professor McGonagall would be proud!",
                "✅ Nice! that's right!✨✨✨",
                "✅ Woh, good job Ace! 🤩",
                "✅ You’ve clearly been studying with Professor Lupin! 📚🐺",
                "✅ That answer was so good, even Snape cracked a smile... almost. 😐✨",
                "✅ Brilliant! You're giving Ravenclaw vibes! 📘🦅",
                "✅ Nailed it! That’s more points for your house! 🏆",
                "✅ Wicked! Even Fred and George would be impressed! 🎇",
                "✅ Yes! That answer was more solid than a Basilisk fang! 🐍💥",
                "✅ On fire! 🔥 You must've borrowed Hermione’s time-turner.",
                "✅ Correcto-mundo! Are you sure you're not a Prefect? 😉",
                "✅ That’s spot on — Professor Flitwick would’ve levitated with joy! ✨🪄",
                "✅ Lumos! You’re lighting this game up! 💡",
                "✅ Mischief *well managed*! 😎",
                "✅ Slughorn: Splendid, my dear! Utterly splendid!",
                "✅ Slughorn: Oh, you remind me of one of my most promising pupils!",
                "✅ Slughorn: Marvelous answer — clearly, talent runs in the family!",
                "✅ Slughorn: Exceptional! Have you considered joining the Slug Club?",
                "✅ Slughorn: That sort of brilliance deserves recognition...as well as crystalized pineapple!",
                "✅ Dumbledore: Ah, yes — wisdom and wit in equal measure.",
                "✅ Dumbledore: Well done! You continue to delight and surprise.",
                "✅ Dumbledore: I dare say your mind is as sharp as Godric’s sword.",
                "✅ Flitwick: Bravo! A textbook-perfect answer!",
                "✅ Flitwick: Outstanding! More points to you!",
                "✅ Flitwick: Oh, very clever indeed!",
                "✅ Flitwick: Yes! That’s the kind of brilliance we love to see!",
                "✅ Flitwick: Delightful! You’re positively beaming with magic!",
                "✅ McGonagall: Correct. Precisely what I expected from a student of your calibre.",
                "✅ McGonagall: Well done. Keep this up and you’ll go far.",
                "✅ McGonagall: Excellent work — more points to your house.",
                "✅ McGonagall: That is the correct answer. Good. Very good.",
                "✅ McGonagall: Quite satisfactory. I shall make note of your progress."
                "✅ Snape: Hmph. Even you get one right occasionally.",
                "✅ Snape: Acceptable. Barely.",
                "✅ Snape: Correct. Try not to look so pleased with yourself.",
                "✅ Snape: I suppose even a cauldron-stirrer like you has potential.",
                "✅ Snape: Remarkable. I didn’t expect that from you... yet here we are.",
                "✅ Lupin: Very well done — you’ve clearly been paying attention.",
                "✅ Lupin: Correct. I knew you'd get there with a little thought.",
                "✅ Lupin: Excellent work — you’re developing quite the sharp mind.",
                "✅ Lupin: Good answer. Quiet confidence suits you.",
                "✅ Lupin: Spot on. Keep up the steady progress.",
                "✅ Lupin: That’s right — never underestimate the power of calm focus.",
                "✅ Lupin: Correct — and more importantly, thoughtfully so.",
            ]
    # Feedback when a player gets the answer wrong (randomly chosen)
    WRONG_ANS_FEEDBACK = [
                "💥 Uh oh! That wasn’t it — but nice try!",
                "💥 Not quite...",
                "💥 Yikes, that's not it.",
                "💥 Oops, a magical misfire!",
                "💥 Wrong answer. Time to consult the magic textbooks?",
                "💥 Nope! Even Dumbledore makes mistakes sometimes.",
                "💥 Sorry, that guess just went up in smoke! 😩",
                "💥 Alas, not the right spell — try again!",
                "💥 Oof! That one got sent straight to Azkaban. 😬",
                "💥 A swing and a miss! Grab your wand and try again.",
                "💥 Oh no, a Confundus Charm might be at work here... 🤔",
                "💥 Uh oh, that answer belongs in the Forbidden Forest!",
                "💥 Close, but no Chocolate Frog. 🐸🍫",
                "💥 Whoa! That spell backfired like Ron’s broken wand! 💫",
                "💥 Nope! That answer went flying like a rogue Bludger. 🏏",
                "💥 Wrong! That wouldn’t even fool a Blast-Ended Skrewt. 🐛🔥",
                "💥 You’ve been bamboozled like Gilderoy Lockhart in a duel!",
                "💥 Missed it! You might need a Remembrall for the next one. 🔴",
                "💥 Yikes! That one fell flat like a failed Wingardium Leviosa.",
                "💥 Accio... wrong answer. 😅 Better luck next time!",
                "💥 The Sorting Hat says... not quite!",
                "💥 Nope! That answer was as off-target as Ron’s first spell.",
                "💥 A troll in the dungeon might've picked a better one. 😅",
                "💥 Sadly, your answer's been eaten by Fluffy. 🐶🐶🐶",
                "💥 Snape: Clearly, you weren’t paying attention. Again.",
                "💥 Snape: Astonishing how wrong that was.",
                "💥 Snape: Do try not to embarrass yourself further.",
                "💥 Dumbledore: Alas, wrong — but curiosity is never wasted.",
                "💥 Dumbledore: I find mistakes to be excellent teachers. Try again.",
                "💥 Dumbledore: The best of us have been wrong before breakfast.",
                "💥 Dumbledore: Success can be found even in the darkest trivia rounds - try again.",
                "💥 Moody: WRONG! CONSTANT VIGILANCE, you fool!",
                "💥 Moody: You’ll get yourself cursed with answers like that.",
                "💥 Moody: That guess was sloppy. Think like a Death Eater would.",
                "💥 Moody: The Dark Arts won’t wait for second chances — focus!",
                "💥 Moody: You’d be stunned in a duel before you hit the buzzer.",
                "💥 McGonagall: That is *not* the correct answer. Do focus.",
                "💥 McGonagall: I suggest you review your notes thoroughly.",
                "💥 McGonagall: Do try to use your brain — that’s what it’s there for."
            ]
    # Feedback / roast for player at the end of a session based on rank (randomly chosen)
    ROASTS: Dict[const.Rank, List[str]] = {
                const.Rank.NOVICE : [
                    "🪄 You’ve got big 'Harry in History of Magic' energy — physically present, mentally on a broomstick.",
                    "🪄 You're like a spell from Lockhart’s textbook — flashy but barely effective.",
                    "🪄 You're the human equivalent of a Bertie Bott’s Every Flavour Bean — mostly bland, occasionally weird, never legendary.",
                    "🪄 You're not even bottom of the class at Hogwarts — you're the forgotten third Hufflepuff in the background of every scene.",
                    "🪄 You give off strong Squib energy — technically part of the magic, but... eh.",
                    "🪄 You're like a first-year’s Lumos — you try, but you’re still not lighting up the room.",
                    "🪄 You're the kind of wizard who'd forget the incantation but still remember everyone's birthdays.",
                    "🪄 You're giving 'passed Potions out of spite and peer support' vibes.",
                    "🪄 You’re not winning House Cup material — but you’d definitely distract the basilisk long enough for someone else to save the day.",
                    "🪄 You don’t stand out in class, but you do make eye contact with the ghost no one else sees, and that’s something.",
                    "🪄 You're the academic equivalent of Quidditch commentary by Luna Lovegood: unexpected, scattered, but weirdly endearing."
                    ],
                const.Rank.ENTHUSIAST : [
                    "🪄 You're not exactly spellbinding — but you do show up, and honestly? That’s kind of heroic.",
                    "🪄 You're basically Neville before year five — full of heart, zero finesse, and accidentally setting things on fire.",
                    "🪄 You’ve got main character energy... just not on this chapter.",
                    "🪄 You're like a misplaced Mandrake: kind of loud, mildly chaotic, but weirdly helpful when it matters.",
                    "🪄 You're the magical equivalent of a decent cauldron cake — sweet, dependable, but no one’s writing home about it.",
                    "🪄 You're like a third-year casting Patronus — there's a wisp, but no one's getting saved just yet.",
                    "🪄 You radiate 'invented a brilliant spell, accidentally cursed the parchment' energy.",
                    "🪄 You're a Ravenclaw in theory — emphasis on theory because the practical part’s missing in action.",
                    "🪄 You're not the Chosen One, but you're definitely the Well-Meaning One.",
                    "🪄 You’d lose your wand in a duel, trip on your cloak, and still somehow pass the exam with a solid Exceeds Expectations.",
                    "🪄 You're like a misfired spell — a little off-target, but occasionally brilliant."
                    ], 
                const.Rank.EXPERT: [
                    "🪄 You're not just top of the class — you're the reason the class has a top.",
                    "🪄 You could make a centaur feel underprepared for a divination exam.",
                    "🪄 You're not the teacher’s pet — you're the teacher’s emergency contact.",
                    "🪄 You're not even studying anymore — you're speedrunning academic greatness.",
                    "🪄 You give off big ‘memorized the entire restricted section for fun’ energy.",
                    "🪄 You're so prepared, you probably packed a bezoar in your lunchbox — just in case."
                    ], 
                const.Rank.MASTER: [
                    "🪄 You're the human version of a perfectly brewed Wolfsbane Potion — complicated, impressive, and honestly, kind of terrifying.",
                    "🪄 You make even Ravenclaws feel underprepared, and they write essays for fun.",
                    "🪄 You're so sharp, I wouldn’t be surprised if your Patronus was a quill correcting someone else’s homework.",
                    "🪄 You’re like Felix Felicis in human form — everything just works out for you, and I resent how impressive that is.",
                    "🪄 You don’t just ace Defense Against the Dark Arts — dark magic sees you and drops its wand.",
                    "🪄 You're the kind of person who would outsmart a Sphinx and then correct its riddle grammar.",
                    "🪄 You’re like a Patronus: rare, dazzling, and showing up just when I thought I was failing.",
                    "🪄 You’re basically the Room of Requirement — always have the answer, even when no one asked.",
                    "🪄 You probably wrote your own spell for productivity — and I bet it scales with deadlines.",
                    "🪄 You're not even in the library anymore — the library is in you."
                    ]
    }
   
    FINAL_SCORE_HH_REACTION: Dict[const.Rank, str] = {
        const.Rank.NOVICE: "{house_head} lets out a quiet sigh. 'Perhaps... reading more would help.'",
        const.Rank.ENTHUSIAST: "{house_head} nods slowly. 'Not bad. You’re starting to show promise.'",
        const.Rank.EXPERT: "{house_head} smiles with approval. 'Excellent work. A fine showing indeed.'",
        const.Rank.MASTER: "{house_head} beams with pride. 'Outstanding! You’ve done {your_house} proud!'"
    }
    
    def __init__(self):
        self.console = Console()  # for using the 'rich' formatting in CLI
    
## VIEW Introduction
    # Game title
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
 
    # display game dedication / acknowledgements
    def print_dedication(self) -> None:
        """
        Acknowledgements for game contributions :)
        This method retrieves the 'dedication' message from the messages dictionary.
        """
        print('\n' + self.INTRO_MESSAGES["dedication"] + '\n') 
            
    # Initial greeting to player 
    def print_greeting(self) -> None:
        """
        Return a warm, whimsical greeting message for the player.
        This method retrieves the 'greeting' message from the messages dictionary.
        Future enhancements might add additional formatting or dynamic behavior.
        """
        # Can add extra behavior later (e.g. game quotes? more formatting? fun facts?)
        print(self.INTRO_MESSAGES["greeting"])
    
    # Player details - a. get their name    
    @staticmethod
    def get_player_name() -> str:
        """Internal method to get player name"""
        print("First, let's get to know you better!")
        while True:
            player_name = input("So what should I call you? Please enter your name: ").strip().title()
            if player_name:
                break
            print("Oops! Please enter a valid, non-empty name.")
        return player_name
    
    # Player details - b. get their Hogwart's house  
    @staticmethod    
    def get_player_house() -> const.House:
        """Internal method to get player's Hogwart house with fun dialogue"""
        
        print("\n\nHmmm, what would your house be....?\n\n")      
        random_house = random.choice(list(const.House)) 
        time.sleep(1.5)  
        print(f"The Sorting Hat thinks you *might* be a good fit for {random_house.upper()}!🎩\n\n ")
        time.sleep(1) 
        
        while True:
            prompt = f"Which Hogwart's house do you choose? (Press Enter to stay in {random_house.value}): " 
            player_house_input = input(prompt).strip().title()
            
            # If the user just hits Enter, input will be empty
            if not player_house_input:
                player_house = random_house  # Accept the suggestion
                break
            # Otherwise, valideate and accept their choice
            try:
                player_house = const.House(player_house_input)
                break 
            except ValueError:
                valid_house_names = [h.value for h in const.House]
                print(f"Uhoh! Please enter a valid house from: {', '.join(valid_house_names)}.")
        
        return player_house
    
    # Print a personalized message based on the player details
    def print_personalized_player_welcome(self, player: Player) -> None:
        """Print a personalized message to welcome them to their house"""
        print("\n---------------------------------------------------------")
        print(f"\n\nWelcome to House {player.house}, {player.name}!\n\n")
        print("---------------------------------------------------------\n")
  
    # Explain game logic to player  
    def explain_gameplay(self, total_questions: int) -> None:
        """
        Return the full explanation of the game’s rules and objectives.

        This method retrieves and concatenates the messages for objective, rules,
        quitting instructions, and the start prompt so that they can be printed together.
        """
        # setup message template for 'how to play' before hand
        template = self.INTRO_MESSAGES["how_to_play"]
    
        # setup list of messages to loop through
        gameplay_sequence = [
            self.INTRO_MESSAGES["objective"] + "\n" + self.INTRO_MESSAGES["tip"],
            template.format(num_questions=total_questions),
            self.INTRO_MESSAGES["how_to_quit"],
            self.INTRO_MESSAGES["start_game"]
        ]
        for message in gameplay_sequence:
            print(message)
            input()
    
## VIEW Game play
            
    def display_question(self, question: Question):
        """Displays a single formatted question."""
        print(f"\n--- Question {question.session_id} ---")
        print(question.question_text)
        
    def get_player_answer(self) -> str:
        """Prompts the player for an answer and returns the input."""
        player_answer = input("Your answer: > ")
        return player_answer
    
    def give_feedback(self, is_correct: bool, correct_answer: str, chances_left: int) -> None:
        """Displays feedback to the player after they answer."""
        if is_correct:
            print(random.choice(self.CORRECT_ANS_FEEDBACK))
        else:
            print(random.choice(self.WRONG_ANS_FEEDBACK))
            print(f"The correct answer is: {correct_answer}")
            if chances_left > 1:
                print(f"Be careful! You have {chances_left} chances remaining.")
            elif chances_left == 1:
                print("Watch out, you have one chance left!")
            
            # can later add special messages: e.g.
            # 1. on a streak (3 questions in a row)
            # 2. relate it to answer keywords
            # 3. Maybe pick one professor / character to give responses through out game?
    
    def display_error(self, message: str) -> None:
        """Displays a generic, formatted error message to the user."""
        # For now, it can be a simple print statement.
        # Later, this is where you would make the text red with rich.
        print(f"\n! ERROR: {message}\n")  
## VIEW Game end    
    def display_final_score(self, score: int, total_questions: int) -> None:
        """Display the final score for the session"""
        print('---- Final Score ----')
        if total_questions > 0:
            percentage = (score / total_questions) * 100
            print(f"You scored: {score} / {total_questions} ({percentage:.1f}%)!!")
    
    @staticmethod  # doesn't rely on specific instance of Class       
    def get_random_feedback_from_key(d: dict, key: Any) -> Optional[str]:
        """Picks a random message from a list in a dict based on a given key."""
        # 1. Retrieve the list of feedback based on the Key.
        message_list = d.get(key)
        
        # 2. Confirm list is not empty and then retrieve a random feedback message
        if message_list:
            return random.choice(message_list)
        
        # 3. Return a default message instead of None for a better user experience.
        return "The Sorting Hat is silent on this matter."
    
    def house_head_reaction(self, rank: const.Rank, player: Player) -> None:
        """ Displays a customized message from the house head based on the Players selected
            Hogwarts house and final rank. """
        # 1. Look up the required player-specific data
        # get house head from the mapping dict
        house_head_name = const.HOUSE_TO_HEAD_MAPPING.get(player.house, "Professor Dumbledore")  # Defaults to Dumbledore if no name found
        # get the House Head feedback string based on rank
        template = self.FINAL_SCORE_HH_REACTION.get(rank) 
        
        # 2. Setup the strings as f-strings with player-specific info
        if template: # incase it can't be constructed - no display, no damage :)
            final_message = template.format(
                house_head=house_head_name, 
                house=player.house.value
            )
            print(f"\n{final_message}")

    def display_player_rank(self, rank: const.Rank, player: Player) -> None:
        """Displays the player's final rank and a corresponding feedback message."""
        # 1. Select a roast based on rank
        roast = self.get_random_feedback_from_key(self.ROASTS, rank)
        # 2. Announce the rank
        print(f'Splendid work, {player.name}! You have attained the rank of "{rank}"! 🏆 \n')
        # 3. Pause to build anticipation
        time.sleep(1.5)  
        # 4. "thinking" ellipsis for some drama✨
        print('...')
        time.sleep(1)
        # 5. Deliver the roast :D
        print(f"\n{roast}")

    def ask_game_renew(self) -> bool:
        """
        Asks the player if they want to play another round.

        Gives the user up to 3 attempts to enter a valid response ('y' or 'n')
        before defaulting to ending the game.

        Returns:
            True if the player wants to play again, False otherwise.
        """
        tries = 0
        while tries < 3:
            prompt = "\nWould you like to play another round? (y/n): "
            renewal_answer = input(prompt).strip().lower()

            if renewal_answer in ['y', 'yes']:
                print("\nExcellent! Preparing a new set of questions...")
                return True
            if renewal_answer in ['n', 'no']:
                return False
            
            tries += 1
            print(f"Sorry, I didn't get that. Please enter 'y' or 'n'. (Attempt {tries} of 3)")

        print("\nToo many invalid entries. Ending the game. Mischief managed!")
        return False 
    
    def display_goodbye(self, player_name: str) -> None:
        """Goodbye message when player quits game"""
        print(f"\nThat was positively enchanting, {player_name}! You've survived a round of magical mischief. ⚡")
        print("Until next time — keep your wand polished and your wits sharper! 🧙‍♀️")
    
    def display_generic_goodbye(self):
        """Displays a generic goodbye message when no player was created."""
        print("\nThanks for playing! Mischief managed. ✨")                    
    
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
        print("DEBUG: GameController initialized.")
    
## CNTL: Initialization

    # Use trivia_manager to setup the questions for the session
    def _setup_session(self, total_questions: int): # State 1
        """Handles the entire data setup process for a new game session."""
        print("Preparing your questions...")
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
        """
    
        # Game title
        self.view.print_ascii_art(font_style='ogre')
        # Game dedication messsage
        self.view.print_dedication()
        # Greeting to the player
        self.view.print_greeting()
        # Initialize player
        player_name = self.view.get_player_name()
        player_house = self.view.get_player_house()
        self.player = Player(player_name, player_house)
        self.view.print_personalized_player_welcome(self.player)
        # Explain game play
        self.view.explain_gameplay(total_questions)

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
        
        # 0. Configuration
        total_questions = const.NUM_QUESTIONS_PER_SESSION
        
        # State 1: Introduction
        self._handle_introduction(total_questions)
        # Guard Clause: Check if player was created successfully before proceeding.
        if not self.player:
            self.view.display_error("Player not created. Aborting game.")
            return False

        # State 2: Data setup
        session_questions = self._setup_session(total_questions)
        # Guard Clause: Check if questions were loaded successfully
        if not session_questions:
            self.view.display_error("Could not load questions for the session.")
            return False


        # State 3: Gameplay loop
        self.current_score = 0
        print(f"\nLet's begin! There are {total_questions} questions in this session.")

        for question in session_questions:
            self._handle_turn(question)
            # make sure they have chances left
            if not self.player.has_chances_left():
                self.view.display_error("Uh oh! You've run out of chances! 🥺")
                break

        # State 4: End game
        return self._end_game(total_questions) # returns bool to main.py (T: another round, F: quit)
    
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
        self.view.display_question(question)
        
        #2. Get the player's answer
        player_answer = self.view.get_player_answer()
        
        #3. Check the answer & chances left
        is_correct = question.check_answer(player_answer)
        
        #4. Provide player feedback on answer
        self.view.give_feedback(is_correct, 
                                question.correct_answer, 
                                chances_left= self.player.get_chances)
        
        #5. update player score and state
        if is_correct:
            self.player.add_score()
        else:
            self.player.lose_chance()

## CNTL: End session    
    def _end_game(self, total_questions: int) -> bool:  # State 4
        """Orchestrates the entire end-game sequence by calling the View."""
        # 0. setup for displaying results
        time.sleep(1)
        print("\n‘Alas, all good things must end...’")
        time.sleep(1)
        print("\n--- Game Over! ---")
        time.sleep(1)
        
        # Guard clause incase player was not instantiated in Introduction - defensive programming to avoid an None state
        if self.player is None:
            self.view.display_error("No player data available to show a final score.")
            # Since there's no player, we can't really ask them to play again.
            return False
        
        # 1. get player final score and display it
        final_score = self.player.score
        self.view.display_final_score(final_score, total_questions)
        
        # 2. Get player rank and display rank and roast! :D
        final_rank = self.player.find_player_wizard_rank(total_questions)
        self.view.display_player_rank(final_rank, self.player)
        
        # 3. Offer another round otherwise quit game
        # a. ask if player wants to continue
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
