"""
=======================================================================
SEMANTIC VERIFICATION ENGINE (Ref implementation: Harry Potter Trivia)
=======================================================================
-----------------------------------------------------------------------
CLI MVP ->  Game View Module
-----------------------------------------------------------------------

"""

import random
import time
from typing import List, Any, Dict#, Optional
from pyfiglet import figlet_format  # to create ASCII art
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.text import Text
from rich.align import Align 
from game_app.player import Player
from game_app.trivia_manager import Question
import game_app.constants as const

        
## GAMEPLAY VIEW MODULE
class GameView:
    """
    Handles all presentation (display) and user input for the trivia game.
    """
## VIEW class atrributes

    # 1.  Colour theme for the `rich` cli formatting package
    THEME = {
        "intro": "bold purple",
        # "question_border": "dark_violet",
        "prompt": "magenta",
        "success": "bold green3",
        "error": "bold red3",
        "feedback": "yellow1",
        "goodbye": "bold purple"
    }

    # 2. Messages used in the various sections of the game introduction
    
    # --- CHARACTER LISTS ---
    DARK_LORD_NAMES = ["lord voldemort", "voldemort", "tom riddle", "sauron", "morgoth"]
    HARRY_ID = ["harry", "harry potter"]
    RON_ID = ["ron", "ron weasley"]
    HERMIONE_ID = ["hermione", "hermione granger"]
    
    INTRO_MESSAGES = {
        "greeting": (
            "⚡️✨ Welcome to the world of magic! ✨⚡️\n"
            "🪄 You've entered the Harry Potter Trivia Challenge!\n"
        ),
        "how_to_play": (
            "🎯 [bold]Goal:[/] Answer {num_questions} questions to earn glory for your House.\n\n"
            "⚡ [bold]Rules:[/] Keep answers short. 3 wrong answers and the game ends!"
            # can add explanations for chances_left and score later
        ),# can consider adding "Aveda Kedavara" as an easter egg for quitting? -> can also use if out of chances! create forbidden wrods list in constants.
        "how_to_quit": (
            "🚪 [dim italic]Type 'quit' at any time to exit.[/]"
        ),
        "start_game": (
            "\n[bold white]Grab your wand, summon your house pride, and let's begin! 🪄[/]"
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
                "✅ McGonagall: Quite satisfactory. I shall make note of your progress.",
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
        const.Rank.MASTER: "{house_head} beams with pride. 'Outstanding! You’ve done {house} proud!'"
    }

    
    def __init__(self):
        # record=True allows to capture the output later
        # width=100 ensures consistent formatting on the web
        self.console = Console(record=True, width=100)  # for using the 'rich' formatting in CLI

    def _create_centered_panel(self, content: RenderableType, style: str, title: str) -> Panel:
        """A helper method to create a styled, centered Panel."""
        return Panel(
             Align.center(content, style=style),
            border_style=style,
            title=f"[{style}]{title}[/]",
            padding=(1, 2)
        )

    def display_error(self, message: str) -> None:
        """Displays a generic, formatted error message to the user."""
        # For now, it can be a simple print statement.
        # Later, this is where you would make the text red with rich.
        self.console.print(f"\n {message}\n", style=self.THEME['error'])

    # def get_latest_view(self) -> str:
    #      """
    #      Retrieves the recorded console output as an HTML string 
    #      and clears the buffer for the next turn.
    #      """
    #      # 1. Export what has been printed to the buffer as HTML
    #      # inline_styles=True ensures colors work without external CSS files
    #      # html_content = self.console.export_html(inline_styles=True, code_format="<pre>{code}</pre>")

    #      # 2. CLEAR the buffer so old text doesn't appear in the next turn
    #      self.console.clear()

    #      return html_content

## VIEW Introduction
    # Game title
    
    def print_ascii_art(self, font_style: str = 'slant'):
        """
        Print the game title as ASCII art in the terminal using the pyfiglet package
        inside a rich Panel.
        
        ### UX IMPROVEMENT: Auto-detects mobile screens ###
        """
        # 1. Clear the screen first so we start fresh
        self.console.clear()
        
        # 2. Check the screen width to see if we are on a phone
        if self.console.width < 60:
            # MOBILE MODE: Simple, clean text header in a panel
            self.console.print(Panel("[bold gold1]HARRY POTTER TRIVIA[/]", style=self.THEME["intro"]))
        else:
            # DESKTOP MODE: Full ASCII art using 'slant' or 'ogre' font
            game_title_text = "Harry Potter Trivia"
            # We use 'slant' here as it is often more readable than standard
            ascii_art_str = figlet_format(text=game_title_text, font=font_style)
            
            # Use the helper function to create display panel
            title_panel = self._create_centered_panel(
                    content=ascii_art_str,
                    style=self.THEME["intro"],
                    title="If cleverness is what you seek, this trivia game will test your peak!!"
            )
            self.console.print('\n\n')
            self.console.print(title_panel)
 
        # Pause slightly so the user registers the title
        time.sleep(1.5)
 
    # display game dedication / acknowledgements
    def print_dedication(self) -> None:
        """
        Acknowledgements for game contributions :)
        This method retrieves the 'dedication' message from the messages dictionary.
        """
        dedication_text = self.INTRO_MESSAGES["dedication"]
        self.console.print(dedication_text, justify="center", style="italic plum2")
        
    # Initial greeting to player 
    def print_greeting(self) -> None:
        """
        Return a warm, whimsical greeting message for the player.
        This method retrieves the 'greeting' message from the messages dictionary.
        Future enhancements might add additional formatting or dynamic behavior.
        """
        # Can add extra behavior later (e.g. game quotes? more formatting? fun facts?)
        greeting_text = self.INTRO_MESSAGES["greeting"]
        self.console.print(greeting_text,justify="center", style=self.THEME["intro"])

    # Player details - a. get their name    
    def get_player_name(self) -> str:
        """Internal method to get player name"""
        self.console.print("First, let's get to know you better!\n", style=self.THEME["intro"])
        while True:
            player_name = self.console.input(
                f"[{self.THEME['prompt']}]So what should I call you? Please enter your name: > [/]"
                ).strip().title()
            if player_name:
                break
            self.console.print(
                f"[{self.THEME['error']}]Oops! Please enter a valid, non-empty name.[/]"
                )
            
        # EASTER EGG :D ... Fun acknowledgement for special names
        name_lower = player_name.lower()
        
        # 1. The Dark Lords
        if name_lower in self.DARK_LORD_NAMES:
            self.console.print(f"\n[{self.THEME['error']}]...Welcome, Dark Lord. We did not expect you.[/] 🐍💀")
        
        # 2. The Golden Trio
        elif name_lower in self.HARRY_ID:
            self.console.print(f"\n[{self.THEME['prompt']}]Welcome, Chosen One. The Boy Who Lived! ⚡[/]")

        elif name_lower in self.HERMIONE_ID:
            self.console.print(f"\n[{self.THEME['prompt']}]Welcome! We expect 110% on this quiz, Miss Granger. 📚[/]")

        elif name_lower in self.RON_ID:
            self.console.print(f"\n[{self.THEME['prompt']}]Welcome, Ron! Don't let the spiders get you! 🕷️[/]")

        # 4. Everyone else
        else:
            self.console.print(f"[{self.THEME['intro']}]\nNice to meet you, {player_name}!! [/]")
        
        time.sleep(1.5)
        return player_name
    
    # Player details - b. get their Hogwart's house  
    def get_player_house(self, player_name:str) -> const.House:
        """Internal method to get player's Hogwart house with fun dialogue"""
        
        # Playful house suggestion by sorting hat as a defaut
        self.console.print("\n\nHmmm, what would your house be....?\n\n", style=self.THEME["intro"])
        
        # EASTER EGG: Houses for dark lords
        name_lower = player_name.lower()
        
        # Default behavior: Random   
        suggested_house = random.choice(list(const.House)) 
        
        # Override for dark lords
        if name_lower in self.DARK_LORD_NAMES:
            suggested_house = const.House.SLYTHERIN
            
        # Get the full style string (e.g., "bold red on gold1")
        house_colour = const.HOUSE_STYLES.get(suggested_house, "default")
    
        time.sleep(1.5)  
        
        # Format the string (text in intro colours, house displayed in house forecolour)
        suggestion_text = Text()    
        # Append first colour text to Text object
        suggestion_text.append(
            "The Sorting Hat thinks you *might* be a good fit for ",
            style=self.THEME["intro"]
        )
        # Append the house name in house colours
        suggestion_text.append(suggested_house.value.upper(), style=house_colour)
        # Append the rest of the text in the intro colours
        suggestion_text.append("!🎩\n\n", style=self.THEME["intro"])
        # Print assembled rich Text object
        self.console.print(suggestion_text)    
            
        time.sleep(1) 
        
        # Prompt player to choose own house if they don't like default
        while True:
            prompt = f"[{self.THEME['prompt']}]Which Hogwart's house do you choose? (Press Enter to stay in {suggested_house.value}): [/]"
            raw_input = self.console.input(prompt)
            # Check for empty input (Default choice) before cleaning
            # (cleaning might turn "   " into "" which is valid default behavior)
            if not raw_input.strip():
                player_house = suggested_house
                break
            player_house_input = ut.clean_input_string(raw_input).title()
            
            # If the user just hits Enter, input will be empty
            if not player_house_input:
                player_house = suggested_house  # Accept the suggestion
                break
            # Otherwise, validate and accept their choice
            try:
                player_house = const.House(player_house_input)
                break 
            except ValueError:
                valid_house_names = [h.value for h in const.House]
                self.console.print(
                    f"[{self.THEME['error']}]Uhoh! Please enter a valid house from: {', '.join(valid_house_names)}.[/]")
        
        return player_house
    
    # Print a personalized message based on the player details
    def print_personalized_player_welcome(self, player: Player) -> None:
        """Print a personalized message to welcome them to their house"""
        # 1. get the house colours 
        house_colour = const.HOUSE_STYLES.get(player.house, "white")
        
        # 2. Create a rich Text object to build the message.
        welcome_text = Text("Welcome to House ", style=self.THEME["intro"])
        welcome_text.append(player.house.value, style=house_colour)
        welcome_text.append(f", {player.name}!",  style=self.THEME["intro"])
        
        # 3. Create the rich panel
        welcome_panel = self._create_centered_panel(
            content=welcome_text,
            style=house_colour,
            title="[bold]A New Contestant![/bold]")
        # 4. Print panel
        self.console.print('\n', welcome_panel, '\n')
        
    # Explain game logic to player  
    def explain_gameplay(self, total_questions: int) -> None:
        """
        Return the full explanation of the game’s rules and objectives.

        This method retrieves and concatenates the messages for objective, rules,
        quitting instructions, and the start prompt so that they can be printed together.
        """
        # 1. Combine Goal/Rules and Quit info into one clean block
        # --> format the 'how_to_play' string with actual number of questions
        rules_content = (
            self.INTRO_MESSAGES["how_to_play"].format(num_questions=total_questions) + "\n\n" +
            self.INTRO_MESSAGES["how_to_quit"]
        )

        # 2. Display the Rules Panel
        self.console.print(Panel(
            rules_content,
            title="[bold gold1]GAME PLAN[/]",
            border_style="purple",
            padding=(1, 2)
        ))

        # 3. Print the "Grab your wand" hype text directly below
        self.console.print(self.INTRO_MESSAGES["start_game"])

        # 4. Pause for user readiness (using the 'tip' message)
        # self.console.print(f"\n{self.INTRO_MESSAGES['tip']}")
        self.console.input()
        
        # 5. Clear screen so Question 1 starts fresh
        self.console.clear()
    
## VIEW Game play
            
    def display_question(self, question: Question, current_score: int):
        """
        Displays a single formatted question.
        ### UX IMPROVEMENT: One question per screen ###
        """
        # 1. Clear the previous screen to remove clutter
        self.console.clear()
        
        # 2. Print a sticky header so score is always visible
        header_text = f"[bold purple]HARRY POTTER TRIVIA[/] | [bold]Score: [green]{current_score}[/]"
        self.console.print(Align.center(header_text))
        self.console.print("\n") # Breathing room

        # 3. Put the question in a Panel to make it the focal point
        question_panel = Panel(
            f"[bold white]{question.question_text}[/]",
            title=f"[cyan]Question {question.session_id}[/]",
            border_style="bright_blue",
            padding=(1, 2)
        )
        self.console.print(question_panel)
        self.console.print("\n") # Space before input prompt
        
    def get_player_answer(self) -> str:
        """Prompts the player for an answer and returns the input."""
        player_answer = self._get_user_input(f"[{self.THEME['prompt']}]Your answer: > [/]")
        return player_answer.strip()
    
    def give_feedback(self, is_correct: bool, correct_answer: str, chances_left: int) -> None:
        """Displays feedback to the player after they answer."""
        
        # Initial spacing (Separate feedback from the user's input line)
        self.console.print()
        
        if is_correct:
            self.console.print(random.choice(self.CORRECT_ANS_FEEDBACK), style=self.THEME['success'])
        else:
            self.console.print(random.choice(self.WRONG_ANS_FEEDBACK), style=self.THEME['error'])
            
            self.console.print()
            self.console.print(f"The correct answer is: {correct_answer}", style=self.THEME['feedback'])
            
            self.console.print()
            if chances_left > 1:
                self.console.print(f"Be careful! You have {chances_left} chances remaining.", style=self.THEME['feedback'])
            elif chances_left == 1:
                self.console.print("Watch out, you have one chance left!", style=self.THEME['error'])
            
            # can later add special messages: e.g.
            # 1. on a streak (3 questions in a row)
            # 2. relate it to answer keywords
            # 3. Maybe pick one professor / character to give responses through out game?

        # ### UX IMPROVEMENT: Pacing ###
        # Force the user to hit Enter so they can read the feedback before the screen clears
        self.console.print("\n[dim italic]Press Enter to continue...[/]")
        self.console.input()
        
## VIEW Game end 
    def display_game_over(self) -> None:
        """Header to print game over before results"""
        time.sleep(1)
        self.console.print("\n‘Alas, all good things must end...’", style=self.THEME['goodbye'])
        time.sleep(1)
        self.console.print("\n--- Game Over! ---\n", style=self.THEME['goodbye'])
        time.sleep(1)
   
    def display_final_score(self, score: int, total_questions: int) -> None:
        """Display the final score for the session"""
        self.console.print('---- Final Score ----', style=self.THEME['goodbye'])
        if total_questions > 0:
            percentage = (score / total_questions) * 100
            self.console.print(
                f"You scored: {score} / {total_questions} ({percentage:.1f}%)!!", 
                style=self.THEME['goodbye'])
    
    @staticmethod  # doesn't rely on specific instance of Class        
    def get_random_feedback_from_key(d: dict, key: Any, default: str = "...") -> str:
        """
        Picks a random message from a list in a dict based on a given key.
        Returns a provided default message if the key is not found or the list is empty.
        """
        # 1. Safely retrieve the list of messages using .get().
        message_list = d.get(key)
        
        # 2. Check if the list exists and is not empty.
        if message_list:
            return random.choice(message_list)
        
        # 3. If the key was not found or the list was empty, return the default.
        return default
    
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
            self.console.print(f"\n{final_message}", style=self.THEME['feedback'])
    
    def display_player_rank(self, rank: const.Rank, player: Player) -> None:
        """Displays the player's final rank and a corresponding feedback message."""
        # 1. Select a roast based on rank
        roast = self.get_random_feedback_from_key(
            self.ROASTS, 
            rank,
            default="unknown... hmmm, you could be a squib?")
        # 2. Announce the rank
        self.console.print(
            f'Alright, {player.name}, you have attained the rank of "{rank.value}"! 🏆 \n',
            style=self.THEME['goodbye'])
        # 3. Pause to build anticipation
        time.sleep(1.5)  
        # 4. "thinking" ellipsis for some drama✨
        self.console.print('...', style=self.THEME['goodbye'])
        time.sleep(1)
        # 5. Deliver the roast :D
        self.console.print(f"\n{roast}", style=self.THEME['feedback'])
        
    def display_final_housepoints(self, final_score:int, player: Player) -> None:
        """Display final points earned by player for their house"""
        house_colour = const.HOUSE_STYLES.get(player.house, "white")
        
        if player.score:
            points_message = f"{final_score} points for {player.house}!!"
            # Create rich panel
            house_points_panel = self._create_centered_panel(
                points_message,
                style=house_colour,
                title='House Points Awarded!')
            self.console.print('\n', house_points_panel, '\n')      
        
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
            prompt_question = "\nWould you like to play another round? (y/n): "
            renewal_answer = self.console.input(f"[{self.THEME['prompt']}]{prompt_question}[/]")
            cleaned_response = ut.clean_input_string(renewal_answer)

            if cleaned_response in ['y', 'yes']:
                self.console.print("\nExcellent! Preparing a new set of questions...\n\n", style=self.THEME['intro'])
                return True
            if cleaned_response in ['n', 'no']:
                return False
            
            tries += 1
            self.console.print(
                f"Sorry, I didn't get that. Please enter 'y' or 'n'. (Attempt {tries} of 3)", 
                style=self.THEME['error'])

        self.console.print(
            "\nToo many invalid entries. Ending the game. Mischief managed!",
            style=self.THEME['goodbye'])
        return False 

    def display_goodbye(self, player_name: str) -> None:
        """Goodbye message when player quits game"""
        self.console.print(
            f"\nThat was positively enchanting, {player_name}! You've survived a round of magical mischief. ⚡",
            style=self.THEME['goodbye'])
        self.console.print(
            "Until next time — keep your wand polished and your wits sharper! 🧙‍♀️\n",
            style=self.THEME['goodbye'])

    def display_generic_goodbye(self):
        """Displays a generic goodbye message when no player was created."""
        self.console.print("\nThanks for playing! Mischief managed. ✨\n", style=self.THEME['goodbye'])

## VIEW Quit game 
    # check if user enters quit        
    def _get_user_input(self, prompt: str) -> str:
        """A private helper to get user input and check for 'quit' command."""
        raw_response = self.console.input(prompt)
        
        # clean input (strip, lower, punctuation)
        command_check_string = ut.clean_input_string(raw_response)
        if command_check_string == 'quit':
            # Raise the exception using the 'const' alias
            raise const.UserWantsToQuit()
        return raw_response  # Answer processing and checking is done by Question
    
    # Display message if player quits in-game:
    def display_quit_message(self):
        """Display goodbye message after a player quits mid-game"""
        self.console.print(
            "Expelliarmus! Your wand — and the game — have been dropped.\nThanks for playing!",
            style=self.THEME['goodbye'])
    
    # Ask if the user wants to save a report of the session's questions for troubleshooting     
    def prompt_to_save_report(self) -> bool:
        """
        Asks the user if they want to save a report of the session's questions.
        Returns True for 'yes', False for 'no'.
        """
        # We can reuse the robust input logic from prompt_for_replay
        prompt = "\n[bold]Did you spot an error? Save a report of this session's questions? (y/n): > [/]"
        response = self.console.input(prompt)
        cleaned_response = ut.clean_input_string(response)

        if cleaned_response in ('y', 'yes'):
            self.console.print("[italic]Saving session report...[/italic]")
            return True

        return False
