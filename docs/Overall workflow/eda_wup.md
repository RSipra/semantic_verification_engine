# data cleaning / EDA writeup

## dont use csv for copying df between notebooks.
repeated error in importing / exporting dfs.
if save as a csv, then lose datatypes because everything is converted to a string.
-> use parquet (data engineering standard)... Its high compression and status as an industry standard make it more versatile. 
-> it needed all columns to be a single type. factual keywords had 1. list of keywords or 2. N/A. refactored method `eda.tag_questions_by_keyword_list()` to return an empty list instead of 'N/A'. Refactored notebook / eda_scripts to handle this better.
-> conflicts in data types. every time .apply is used with a lambda function to the token columns that contain a list of items,  then pandas converts them to np.darray type instead for efficiency ... had to refactor methods that dealt with token columns to be flexible enough to handle both lists and np.darrays

while editing 
- how to handle multiple keywords? realized 'factual_recall_keywords' were not ordered. -> reordered
- created new column called "main_keyword" - select the first one in the case there are multiple keywords from the list.
- refactored pipeline and filter method to then use 'main_keyword' column -- SOC made making these changes very easy. Only had to edit code in 4(?) places.

as a paragraph to be edited: 

## Refactoring the EDA Pipeline: A Lesson in Robustness
During the exploratory data analysis, a key task was to categorize questions by their primary interrogative keyword (e.g., "what," "who"). My initial approach created a list of all factual-recall keywords found in a question, but I soon discovered a critical flaw: the list didn't preserve the order in which the words appeared. This was a problem for questions containing multiple keywords, such as "Who knows what happened?"

To solve this, I first refactored the tagging function to ensure the keyword list was correctly ordered. Next, to create a definitive category for each question, I engineered a new feature column called main_keyword. This column is populated by a simple rule: if a question has multiple interrogative keywords, select the first one as the primary category.

The most satisfying part of this process was how easy the changes were to implement. Because the eda_scripts module was built on a Separation of Concerns (SOC) design pattern, I didn't have to rewrite the entire script. I only needed to update the specific helper functions responsible for data preparation and filtering—just a few targeted edits—and the rest of my analysis pipeline worked seamlessly with the new, more robust main_keyword column. This experience was a great real-world lesson in how thoughtful code architecture pays dividends down the line.

## Development of a Rule-Based Answer Classifier
- Initial Goal: To move beyond a simple boolean is_numeric flag and create a multi-class classifier for answer types (text, numeric, date, year) to enable more robust answer-checking logic.

- Learning #1: Choosing the Right Tool: The initial idea of using a semantic model like Sentence-BERT was discarded. We determined that this task is about syntactic pattern recognition, not semantic understanding. A rule-based approach using regular expressions and specialized libraries (pandas.to_datetime) was chosen as the far more efficient and accurate tool for the job.

- First Draft: Hierarchical Logic: The first version of the function established the core principle of a hierarchical check. It tested for the most specific patterns first before moving to more general ones, following the order: date → year → numeric → text. This prevents a year like "1994" from being misclassified as a generic number.

- Learning #2: Discovering Flaws with Test-Driven Development (TDD): A comprehensive test suite was built using pytest fixtures with a wide range of standard formats and tricky edge cases. The subsequent test failures were not setbacks but the primary driver of improvements, pinpointing specific flaws in the logic.

- Refinement #1: Fixing Edge Cases Uncovered by Tests:
    - The initial date logic was too simple, failing to recognize ISO-formatted dates (e.g., "2025-08-29") because it expected letters to be present.
    - The initial year logic was too restrictive, failing to identify historical formats (e.g., "65 BC").
    - The year logic was also too aggressive, incorrectly classifying text that simply contained a year-like number (e.g., "Nimbus 2000") as a 'year'.

- Learning #3: Leveraging Existing Data for Efficiency: A key insight was to use the existing is_numeric_answer flag from the data ingestion pipeline as a pre-filter. This optimized the function significantly by immediately classifying all non-numeric answers as 'text' first, reserving the more computationally expensive parsing checks for the smaller subset of answers that actually contained numbers.

- Refinement #2: Clarifying the Specification: The test case for "Warlock's Convention of 1709" forced a decision. We concluded that the primary subject was the event, not the year, so the correct classification should be 'text'. This was a crucial learning point: the process refined not only the code but also the definition of what each category meant, leading to an update in the test fixture itself.

- Final Result: The final function is a robust, efficient, and well-tested classifier. It combines a simple boolean pre-filter with a precise, hierarchical set of parsing rules to accurately categorize a wide variety of answer formats. 💡

## Unveiling Our Trivia Master: The Evolution of Our Harry Potter Question Classifier
Building a robust trivia system isn't just about questions and answers; it's about understanding the type of question being asked. Our Harry Potter trivia project relies heavily on a sophisticated Question Classifier to categorize each prompt, enabling more intelligent game mechanics and precise answer validation.

Today, we're taking you behind the scenes to explore the journey of our classifier, highlighting its current capabilities and an exciting upcoming enhancement.

**Why Categorize Questions? The Power of "Knowing Your Type"**
Imagine a quiz where a "What is...?" question expects a one-word answer, but another "What is...?" demands a full explanation. Without categorization, the system treats them the same, leading to frustration for players and complex logic for developers.

Our classifier addresses this by assigning a question_type (e.g., Factual Recall, Explanatory, Yes/No, Multiple Choice) to every question. This allows us to:
- Tailor Answer Validation: Factual Recall (FR) questions can use direct keyword matching, while Explanatory (EX) questions might require more advanced semantic similarity checks.
- Enhance User Experience: Future game modes could adapt to question types, offering hints differently or even restricting certain types for specific challenges.
- Improve Data Understanding: Categorization provides valuable insights into the composition of our trivia dataset, helping us identify gaps or over-represented areas.

**Recent Victories: The Current State of the Classifier**
We've made significant strides in refining our categorize_question function, incorporating nuanced logic to handle the trickiest interrogative keywords. Here's a quick rundown of its current capabilities:
- Direct Keyword Mapping: Questions starting with terms like "who," "where," or "when" are efficiently identified as Factual Recall (FR).
- Yes/No & Multiple Choice: Explicit patterns for "True/False," "Yes/No," and questions followed by a list of options are robustly classified as YN or MCQ respectively.
- "How" Questions: A Hybrid Approach: We've successfully implemented a hybrid rule for "how" questions. If a "how" question contains specific factual n-grams (e.g., "how many," "how old"), it's tagged as Factual Recall (FR). Otherwise, it defaults to Explanatory (EX), anticipating a process or description. This ensures questions like "How many Horcruxes did Voldemort create?" are correctly distinguished from "How does one apparate?"

These updates ensure a solid foundation, providing clear distinctions for the majority of our trivia questions.

**The Next Frontier: Taming the "What" Question (Pending Enhancement)**
As powerful as our classifier is, there's always room for improvement. Our next major enhancement targets the ambiguous "what" question.

The Problem: Currently, all questions starting with "what" are categorized as Factual Recall (FR). However, "what" can be used in two distinct ways:
- Factual: "What is the name of Harry's owl?" (Answer: "Hedwig")
- Explanatory: "What is a Horcrux?" (Answer: "An object in which a person has concealed part of their soul.")

Treating both as FR isn't ideal, as the latter clearly demands an explanatory answer.

**The Solution: A Data-Driven Hybrid Approach:**
Our plan is to implement a hybrid rule similar to our "how" logic. We'll leverage the answer length as a key differentiator. After performing a quick Exploratory Data Analysis (EDA) on existing "what" questions, we expect to find a clear cutoff point for answer length:
- Short Answers (answer_length <= X words): Will be classified as Factual Recall (FR).
- Long Answers (answer_length > X words): Will be classified as Explanatory (EX).

This enhancement will ensure that our classifier becomes even more precise, dynamically adapting its classification based on both the interrogative keyword and the expected complexity of the answer.

**What's Next?**
This upcoming update represents a crucial step in our journey towards a truly intelligent trivia system. Once implemented and thoroughly tested, this will allow us to further automate our data ingestion pipeline, requiring even less manual input for new questions.

Stay tuned for more updates as we continue to refine our trivia master!

## Keeping Our Trivia Smart: Why We Retrain Our TF-IDF Vectorizer After New Data
In the world of Natural Language Processing (NLP), a model is only as good as the vocabulary it understands. As we continuously enrich our Harry Potter trivia dataset with hundreds of new questions and answers, a critical maintenance task emerges: updating our TF-IDF (Term Frequency-Inverse Document Frequency) vectorizer.

This isn't just about adding new data; it's about making sure our system understands that new data in the context of all our data. Let's dive into why this step is so vital for preventing "vocabulary drift" and keeping our trivia system sharp.

**The Role of TF-IDF: Our Lexical GPS**
Before a computer can 'understand' text, that text needs to be converted into a numerical format. TF-IDF is a common and powerful technique for this. It generates a numerical representation (a vector) for each question and answer, where:
- Term Frequency (TF): Measures how often a word appears in a document (question/answer).
- Inverse Document Frequency (IDF): Measures how unique or important a word is across all documents in our entire dataset. Words like "the" or "is" get a low IDF score, while "Horcrux" or "Hogwarts" get a high IDF score, indicating their importance.

When combined, TF-IDF gives us vectors that highlight the most distinctive words in each piece of text. These vectors are then crucial for tasks like:
- Duplicate Detection: Comparing vectors to find questions that are semantically very similar.
- Question Type Classification: Features derived from these vectors can feed into more advanced classifiers.
- Future Answer Evaluation: Understanding the core concepts in a user's answer.

**The Challenge: Vocabulary Drift with New Data**
Our initial TF-IDF vectorizer was built on a foundational set of Harry Potter trivia. It learned its IDF scores (the "importance" of words) from that specific vocabulary.

Now, imagine we add 500+ new questions. These questions inevitably introduce:
- Entirely New Words: Perhaps characters, spells, or locations not present in the original dataset. If our vectorizer hasn't 'seen' these words before, it won't be able to generate a vector for them, effectively ignoring valuable information.
- Changes in Word Importance: A word that was rare (high IDF) in the old dataset might become common (lower IDF) in the new data, or vice versa. If we don't update the vectorizer, its IDF scores will be outdated, misrepresenting the true importance of words.

This discrepancy between the vocabulary and word importance learned by the old vectorizer and the reality of the expanded dataset is what we call vocabulary drift. It can silently degrade the performance of any downstream task that relies on these text representations.

**The Solution: Retraining Our Vectorizer**
To combat vocabulary drift and ensure our trivia system remains accurate, we periodically retrain our TF-IDF vectorizer on the entire, updated dataset.

The process is straightforward but essential:
- Combine Data: After new questions are successfully ingested and standardized into our main trivia DataFrame, we have a single, comprehensive dataset.
- Re-fit the Vectorizer: We take our TfidfVectorizer instance and fit it again on the combined 'question' and 'answer' texts from this new, larger dataset.
- Transform All Text: Once fitted, we use this newly trained vectorizer to transform all existing questions and answers, generating fresh, up-to-date TF-IDF vectors for every entry.

This simple but powerful step ensures that:
- New vocabulary is learned: The vectorizer now recognizes and can encode every word present in the expanded dataset.
- IDF scores are accurate: The importance of each word is recalculated based on its frequency across all current questions and answers.
- Consistency is maintained: All text representations are generated using the same, most current understanding of our dataset's language.

**Looking Ahead**
Regularly updating our TF-IDF vectorizer is a critical part of our data maintenance strategy. It ensures that as our Harry Potter trivia universe grows, our NLP tools grow with it, maintaining the accuracy and intelligence of our system. It's one of the unsung heroes working behind the scenes to keep our trivia challenging, fair, and fun!

## 