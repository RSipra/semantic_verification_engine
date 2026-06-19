# 📜 Data Sources for Harry Potter Trivia Game

This document tracks the datasets used in this project, their sources, and any modifications made.

---
## 📌 1. Trivia Questions Dataset  
- **Source**: Hugging Face  
- **URL**: [https://huggingface.co/datasets/saracandu/harry-potter-trivia-human](https://huggingface.co/datasets/saracandu/harry-potter-trivia-human)  
- **Description**: A publicly available dataset of Harry Potter trivia questions and answers. The original raw dataset is located [here](data/original_dataset_DONT_TOUCH/harry_potter_trivia_questions_HFdataset.csv). It is recommended that this file remains unmodified to preserve the original raw data. Any data cleaning or processing should be done in separate scripts or in memory within the game logic. The modified datasets for this project are [here](data/Working%20files/).
- **Modifications in processed dataset:** This project involved the following modifications to the original dataset:
  - Cleaned the data by merging train and test datasets and removing the `text` column and duplicate entries.
  - Tokenized the questions and answers for Natural Language Processing (NLP) tasks into keywords.
  - **Planned Future Modifications:** Assigning difficulty levels based on token complexity and adding a column for Named Entity Recognition (NER) predictions to use for categorization.
- **License:** Believed to be under the Apache License 2.0.
- **Note:** A local copy of the original dataset is being used for this project since the original source is now unavailable. 

---
## 📌 2. Harry Potter Corpus
- **Source**: R package on GitHub
- **URL**: [https://github.com/bradleyboehmke/harrypotter]https://github.com/bradleyboehmke/harrypotter)
- **Description**: A collection of the full text of the seven main Harry Potter books, originally packaged for R in .rda format. These files were read into Python using the pyreadr library.
- **Usage**:   Serves as the canonical source text for the LLM-based question generation process. This ensures that all new questions are factually grounded in the main book series.
- **License**: Not specified in the source repository. Used here for a non-commercial portfolio project.

---
## 📌 3. Harry Potter Character List  
- **Source**: GitHub Repository  
- **URL**: [https://gist.github.com/jennynz/7eaf7ea4eeb3d686b19e997e721bda0c](https://gist.github.com/jennynz/7eaf7ea4eeb3d686b19e997e721bda0c)  
- **Description**: A list of all 689 Harry Potter characters.  
- **Usage**: Planned: Use to create a gazetteer for the custom Named Entity Recognition (NER) model, which helps with entity validation and question categorization.

---
## 📌 4. AI-Generated Assets
- **Source**: Generated using [recraft.ai](https://www.recraft.ai/) / AI-powered design tool and [replicate.com/fofr/consistent-character](https://replicate.com/fofr/consistent-character?prediction=erdt5f9fm5rme0cmeqcbjczbb8) / Create images of a given character in different poses.
- **Description**: Custom images for the game UI and persona, including different poses, gestures, and expressions for the game's MC.
- **Usage**: Game backgrounds, logo, and illustrations for major trivia themes and the MC persona.

---
<!---## 📌 5. Sound Effects & Background Music  
- **Source**: Free Sound Effects Library (Placeholder)
- **URL**: [xx](xx)  
- **Description**: Collection of magical sound effects for game feedback.  
- **Usage**: Correct/incorrect answer sounds and background music.

---
## 📌 6. Additional Notes  
- All external datasets are used under their respective licenses.  
---
