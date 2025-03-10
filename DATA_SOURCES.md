# 📜 Data Sources for Harry Potter Trivia Game

This document tracks the datasets used in this project, their sources, and any modifications made.

---

## 📌 1. Trivia Questions Dataset  
- **Source**: Hugging Face  
- **URL**: [https://huggingface.co/datasets/saracandu/harry-potter-trivia-human](https://huggingface.co/datasets/saracandu/harry-potter-trivia-human)  
- **Description**: A dataset of Harry Potter trivia questions and answers.  
- **Modifications**:  
  - Cleaned the data (merged train / test datasets, removed `text` column, duplicates).  
  - Tokenized the questions and answers for NLP tasks.  
  - Planned: Assign difficulty levels based on token complexity / Added a column for Named Entity Recognition (NER) predictions.  

---

## 📌 2. Harry Potter Character List  
- **Source**: GitHub Repository  
- **URL**: [https://gist.github.com/jennynz/7eaf7ea4eeb3d686b19e997e721bda0c](https://gist.github.com/jennynz/7eaf7ea4eeb3d686b19e997e721bda0c)  
- **Description**: A list of all 689 Harry Potter characters.  
- **Usage**:  
  - Planned: Used for Named Entity Recognition (NER) model training / Helps categorize trivia questions based on character mentions.  

---

## 📌 3. Sound Effects & Background Music  
- **Source**: Free Sound Effects Library  
- **URL**: [xx](xx)  
- **Description**: Collection of magical sound effects for game feedback.  
- **Usage**:  
  - Correct/incorrect answer sounds.  
  - Background music for atmosphere.  
  - Planned: Sound cues for special achievements.  

---

## 📌 4. AI-Generated Images  
- **Source**: Generated using [recraft.ai](https://www.recraft.ai/) / AI-powered design tool 
- **Description**: Custom images for game UI and storytelling.  
- **Usage**:  
  - Game backgrounds, logo, and game MC persona.  
  - Illustrations for major trivia themes.  

---

## 📌 5. AI-Generated Images  
- **Source**: Generated using [replicate.com/fofr/consistent-character](https://replicate.com/fofr/consistent-character?prediction=erdt5f9fm5rme0cmeqcbjczbb8) / Create images of a given character in different poses.
- **Description**: Custom poses of game MC person with different gestures and expressions.  
- **Usage**:  
  - Generate multiple poses for main game MC persona for different instances in the game.   

---

## 📌 6. Additional Notes  
- All external datasets are used under their respective licenses.  
 

---

### 📌 **Contributing**  
If you find a better dataset or need updates, submit a pull request or open an issue on GitHub.

---

