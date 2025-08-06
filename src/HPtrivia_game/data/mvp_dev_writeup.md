Initially, the idea was to create a quick and simple CLI MVP (or Command-Language-Interface Minimum Viable Product... a mouthful!). To start I wrote down the high-level sequential steps of what the game would involve and the began translating them to code. 

For coding, the idea was straightforward, get the game running fast: a few OOP classes in a single file, handling everything from loading data to running the game loop. But as I started building, it quickly became clear that things were getting tangled. That’s when I started thinking about Separation of Concerns (SoC) and exploring the Model-View-Controller (MVC) pattern.

### Why the MVC pattern?

While a single script might have been faster for a quick prototype, after some research and planning, I decided to use the Model-View-Controller (MVC) pattern with the larger goals of the project in mind. Setting up the code this way meant an upfront overhead (learning, time to apply it), but the long term gains made it worth it. So yes, it took a little more thinking at the start, but that decision will make the work in late Phases smoother, more scalable, and way more polished.

The Model-View-Controller (MVC) pattern is a popular software design architecture used to organize an application into three components maintaining a clean separation of concerns. The Model is the core of the application; it manages the data, logic, and rules. The View is the user interface; it's responsible for all presentation and user interaction only. Finally, the Controller acts as the brain, receiving input from the View, telling the Model what to do, and then updating the View with the results. 

![Generic MVC logic](https://media.geeksforgeeks.org/wp-content/uploads/20240219101004/MVC-Design-Pattern-.webp)
*General layout of an MVC app*

The MVC pattern is very well suited to the game because:

1. it helps me isolate the complex logic into different classes by their tasks. The "heavy-lifting" is done by the \`GameController\` (game logic), \`Trivia\` (data loading and verification), and eventually \`Question\` (semantic answer checking). The \`View\` class logic is relatively straight forward with the CLI.
2. It allows for adaptability and scalability. By separating the data (Model), presentation (View), and logic (Controller), the application becomes incredibly flexible. 
    - So the upgrade of the user interface from a CLI to a web page in Phase 3 would only require swapping out the View component, leaving the core game engine untouched.
    - Adding a new feature, like semantic answer-checking, is much simpler and cleaner. I will only need to modify the \`Question\` class, without any ripple-effects on the rest of the game.
3. It makes managing the state of the game easier. The trivia game has a lot of states to track, for example the player's score, chances left, which question is next, whether the game is over. MVC gives this state a clear home.

### How the MVP iteratively took shape

Initially, I began with three basic modules, following the MVC archetype:
- A Question module to load and store trivia questions
- A Player class to track player details
- A Controller to run the game

It worked in theory, but in practice, the boundaries were still fuzzy and the responsibilities were overlapping. That’s when the real design journey began with many iterations of learning and development. The guiding principles were to learn good coding practicses and create a professional polished product while managing time and scope efficiently. Some of the notable iterations were:

#### Iteration 1: I needed a \`Trivia\` class.
The first big refactor was carving out a dedicated Trivia class from the Question class. Its job? Just handle the dataset—load it, clean it, and return a random subset of questions for a game session. And let the Question class handle everything to do with a single question - define its attributes, check answers.

#### Iteration 2 & 3: An \`Introduction\` class and its transformation into the \`View\` class/
At first, I had a separate \`Introduction\` class just for the welcome messages and player setup. But as I built the rest of the game—question prompts, feedback, end screen, I realized they all followed the same pattern: displaying text and gathering input. That class evolved into \`GameView\`, which now owns all terminal I/O. Whether it’s the intro, the gameplay loop, or the “Play Again?” prompt—it all runs through the \`GameView\`.

#### Iteration 4: The side quests (that mattered)
Development is never a straight line. While working on Trivia's data loading, I hit two important "side quests"
- **Side Quest 1**: I built utils_path.py, a small utility module to reliably locate files regardless of environment. It started as a convenience and ended up becoming a core helper for file operations across the game.

- **Side Quest 2**: I cleaned the raw trivia data in Jupyter notebooks and standardized it for use in the game. It wasn’t glamorous, but it saved me countless hours down the line and made the data pipeline rock-solid. This is discussed in XX/

#### Iterations 5–8: Polishing and final assembly
Now that the foundation was solid, it was time to bring the whole game together:
- **The Controller**: I built out the game loop, tied together the Trivia model and the GameView, and managed all transitions between game states.
- **Rich Console UI**: I swapped out basic print() calls for styled output using the rich library. The result? A much more immersive and polished CLI experience.
- **Centralizing Constants**: To avoid "magic strings" and make the code more maintainable, I created a constants.py module to store Enums (for house, rank, colors) and magic values. Cleaner, more readable, and easier to update.
- **Handling "Quit"**: I introduced a global QuitGameException, making it easy to gracefully exit the game from anywhere the player types "quit".
- **The Happy Path 😁**: Finally, I played through the entire game manually, end-to-end. The logic worked, the design held up, and it felt cohesive.

#### The final architecture: clean, modular, MVC-Inspired
What started as a single-file game idea evolved into a clean, modular codebase with clear separation of concerns:

- \`Trivia\` (Model) handles the dataset.
- \`Player\` (Model) stores the player info.
- \`GameView\` (View) handles all the input and output.
- \`GameController\` (Controller) manages logic and game state.
- \`Constants\` (infrastructure) holds enums, magic values, and quit exception.
- \`main.py\` wires everything up by creating instances and injecting dependencies

![Phase 1 CLI MVP software architecture based on the MVC pattern](src/data/nlp-engine/mvp_architecture.svg)

### Up Next: Phase 1.5 (Testing) & Phase 2 (NLP features)
With the MVP up and running, the next step is automated testing using pytest. I want to create a safety net before I move on to Phase 2 integrating NLP features like semantic answer-checking.


learning: 
The biggest lesson from this project was that the final, working code is just the end result of a much more interesting story of problem-solving and design. The process of starting with a simple idea and iteratively refactoring it based on professional patterns like MVC is what transforms a simple script into a robust piece of software. 