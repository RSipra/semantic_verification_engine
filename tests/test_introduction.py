# Testing Introduction class - core logic MVP - manual testing.
from dotenv import load_dotenv
load_dotenv() 
from HPtrivia_game.controller import Introduction as intro

# # Individual methods:

# Initialize intro instance:
# introduction = intro()
# #1.a. Print ASCII Art:
# intro.print_ascii_art()
# # #1.b. Print ASCII Art: custom font
# intro.print_ascii_art(font_style='digital')
# intro.print_ascii_art(font_style='ogre')

# # # 2. Greeting
# print(introduction.greet())

# # # 3. get player info():
# intro.get_player_details()

# 4. explain the game:
# print(introduction.explain_gameplay())
# print(gameplay)

# Full Introduction:
introduction = intro()
intro.print_ascii_art(font_style='ogre')
print(introduction.greet())
intro.get_player_details()
print(introduction.explain_gameplay())
