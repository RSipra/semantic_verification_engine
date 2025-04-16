# 🧙‍♀️ Hogwarts Trivia Game – A Passion Project Turned Portfolio Spell 🌟

This repository contains the source code, notebooks, and support documents for a Harry Potter trivia game built with Python featuring NLP-driven features.

This magical little adventure started over late-night book readings and a daughter who just won’t stop dropping Harry Potter trivia around the clock. Naturally, a trivia game was born – for her to play, and for me (a muggle-turned-data-wizard) to build.

This is more than just a game — it’s a portfolio project to practice and showcase:

- 🐍 Clean Python + OOP design
- 🧠 NLP & Named Entity Recognition (NER) spells. 
- 🎯 Building an MVP from idea to deployment (Command logic interface → Web App)
- 📦 Packaging, modular design & installable project structure
- 🧪 Testing, versioning, and all those responsible grown-up dev things
- 🦄 Use of DistilBERT for some really cool magic!✨ (semantic matching of answers, more conversational play, etc!) 

Whether you're here to cast code spells or just play a few rounds of trivia, welcome to a corner of the internet where passion meets Python.

## Table of Contents

1. [Description](#description)
2. [Project development phases](#project-development-phases)
3. [Features](#features)
4. [Tools & Technologies Used](#️-tools--technologies-used)
5. [Installation](#installation)
6. [Usage](#usage)
7. [Controls](#controls)
8. [Data Sources](#data-sources)
9. [License](#license)
10. [Contributing](#contributing))
11. [Acknowledgements](#acknowledgements)
12. [Disclaimer](#disclaimer)

## Description

Step into the halls of Hogwarts and test your knowledge with this interactive CLI trivia game (and later a web app)! Challenge yourself or compete for house points against a series of randomly selected questions drawn from the wizarding world. This project goes beyond simple Q&A, utilizing Natural Language Processing (NLP) with custom-trained models [Phase 2 onwards] to understand the nuances of the questions and eventually [Phase 4+] even your answers!


<details>
## <summary>Project development phases</summary>

The main steps in the devleopment of the game are:

1. Phase 1: MVP core game logic, unit testing, and pattern awareness
    - Setup environmental and data foundation (download, cleaning, EDA, preprocessing of dataset)
    - Develop basic core logic and OOP structure for CLI game play                  *<-- Current phase*
    - Test and refactor the game throughly (using unittest and pytest)

2. Phase 2: NLP / NER integration to CLI MVP.
    - Annotation of data, training of NER model with iterative active learning.
    - static NER tagging
    - Integrate logic into MVP (topic and difficulty level selection)

3. Phase 3: Basic web app (with Flask)
    - setup and integrate game logic backend with audio and visuals.
    - styling and deployment prep.

4. Phase 4+: Enhancements! (the most exciting part)
    - runtime NLP with DistilBERT (semantic answer checking, smarter hints, etc)
    - tagging reference of q&a to HP book of origin
    - easter eggs and themed commands / elements
    - GUI and game state enhancements 

**Project documentation**:

The project phases and sprints can be found in the detailed workflow document. This is a live, adaptive document to organize work and learning streams of the project.
- [🗂️ Latest Workflow](docs/Overall%20workflow/) — Always updated with the current workflow version.  
- Older versions are stored in [`/docs/superceded/`](docs/superceded/) for reference.
</details>

## Features

### Current features:
- **Randomized Trivia Questions**: Every game session is unique.
- **Scoring**: Represent your chosen Hogwarts house and earn house points to find your wizarding trivia rank.
- **Interactive UI**: Command logic interface with dialogue and feedback to create an immersive experience.

### Future features:
- **Custom NER Model**: support topic selection (e.g. characters, locations, spells) and difficulty-level questions in the game based on custom NER class tagging.
- **Interactive GUI**: web based up for more player engagement with visuals, audio, and interactive elements.

<details>

## <summary>🛠️ Tools & Technologies Used</summary>

- Python – Core language for game logic, data processing, and NLP components
- NLTK / spaCy – Natural Language Processing (NER and text analysis)
- Jupyter Notebooks – Used for exploratory data analysis and prototyping
- Git / GitHub – Version control and collaboration
- VS Code – Primary development environment
- Markdown – Documentation and workflow planning

📦 See [requirements.txt](requirements.txt) for packages required to run the game, and [requirements-dev.txt](requirements-dev.txt) for the complete list of tools used in notebooks, data processing, and advanced NLP work.

💡 AI-assisted support from ChatGPT 4o (free-tier), and Google Gemini 2.5 Pro (experimental, free-tier) was used for brainstorming, project planning and strategizing, code review, ideation, debugging and learning throughout development.
</details>

## Installation

This section will provide clear, step-by-step commands to install game once ready.
<steps such as: git clone.. cd.. pip install setup.py... run main.py etc>

## **Usage**

1. When you launch the game, you will be prompted to enter your name and select your Hogwarts house.
2. Answer a series of randomly selected trivia questions about the Harry Potter universe.
3. After each question, you will receive feedback on whether your answer is correct or incorrect.
4. At the end, you'll receive a score and a "Wizard Rank" (e.g., "Harry Potter Expert," "Hogwarts First-Year").

## Controls:
- Type your answer and press **Enter** .
- Type "quit" to exit game at any point.

## Data Sources

For more information on the datasets used, please refer to the [Data Sources file](DATA_SOURCES.md).

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

## Contributing

We welcome contributions to improve the game! Here’s how you can help:

1. Fork this repository.
2. Create a branch for your feature or bug fix (`git checkout -b feature-name`).
3. Commit your changes (`git commit -am 'Add new feature'`).
4. Push to the branch (`git push origin feature-name`).
5. Open a pull request.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md) and ensure your changes are well-documented.

## Acknowledgements
To my daughter — an endless source of joy and inspiration. You brought the *fun* to this project, and are my go-to expert for all things Harry Potter, especially those rapid-fire and obscure references. Thank you for being my alpha/beta tester and ever-patient reviewer!

## Disclaimer:
This project is an unofficial fan tribute to the Harry Potter series and is not endorsed by or affiliated with J.K. Rowling, Warner Bros., or any related parties. It is a passion and learning project created solely for educational and non-commercial purposes.
