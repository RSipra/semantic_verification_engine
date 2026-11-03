# 📜 Data Sources for Harry Potter Trivia Game

This document tracks the datasets used in this project, their sources, and any modifications made.

---
## 📌 1. Trivia Questions Dataset  
- **Source**: Hugging Face  
- **URL**: [https://huggingface.co/datasets/saracandu/harry-potter-trivia-human](https://huggingface.co/datasets/saracandu/harry-potter-trivia-human)  
- **Description**: A publicly available dataset of Harry Potter trivia questions and answers. The original raw dataset is kept unmodified in the DVC raw-data stage (`data/01_raw/trivia_dataset_v0_raw.csv`). All cleaning and 
processing happens in later stages. Processed datasets live in the numbered DVC stages under `data/`
 (DVC-tracked, not included in the repo; see Access below).
- **Modifications in processed dataset:** This project involved the following modifications to the original dataset:
  - Cleaned the data by merging train and test datasets and removing the `text` column and duplicate entries.
  - Tokenized the questions and answers for Natural Language Processing (NLP) tasks into keywords.
  - **Planned Future Modifications:** Assigning difficulty levels based on token complexity and adding a column for Named Entity Recognition (NER) predictions to use for categorization.
- **License:** Believed to be under the Apache License 2.0.
- **Note:** The original Hugging Face dataset is no longer available. This project uses a local copy, versioned
   with DVC in a private remote. The one-off download script
   (`scripts/pipelines/download_dataset_from_huggingface.py`) was removed on 2026-11-03, since the source no longer
   exists; it remains in git history.
 - **Access:** The dataset is not redistributed with this repository. The questions derive from copyrighted source
   material, and the dataset's own license could not be confirmed. Cloning the repo does not include the data;
   `dvc pull` requires access to the project's private remote. 

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
