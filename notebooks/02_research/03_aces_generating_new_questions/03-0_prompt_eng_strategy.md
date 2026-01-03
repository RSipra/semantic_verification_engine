# 3: Content Factory: Synthetic question generation pipeline

## 3-0: Prompt engineering strategy

# 1: Introduction
The goal of this project is to create an engaging Harry Potter trivia game that is more intuitive and flexible than typical multiple-choice formats found online. It will leverage Natural Language Processing (NLP) to handle fluid, free-text player responses, for a more intuitive, interactive, and engaging experience for the player. This capability for flexible answer checking is a key differentiator to game formats commonly available for fans. 

in this notebook, LLM models will be used to generate new trivia questions with the following aims:

1. **Balance the current Baseline dataset**: In the [previous EDA notebook](../02_eda_and_deduplication.ipynb), two key imbalances were identified within the baseline (v1) dataset. Nearly 80% of the questions are straight fowards Factual Recall (FR) types with short answers (1-3 words), and many are sourced from auxiliary content rather than the core seven books. To create a more varied and engaging gameplay experience, we need to address these gaps. Adding more Explanatory (EX) questions is a top priority, as they are more thought-provoking, creating a richer experience for fans that enjoy deep lore. It also creates the perfect opportunity to implement semantic answer checking. Increasing the number of Multiple-Choice (MCQ) and Factual Recall (FR)) questions will also be crucial for managing difficulty within a game session.
2. **Train the SentenceBERT model with domain specific terminology**: Because these questions are being generated from scratch, the LLMs can produce variations in answers to each question to help train the model to recognize variability from a Player's answers. The questions and answers should also richly represent the Harry Potter specific terminology and correctly based on lore.

### How to Read the Prompt Engineering Notebooks
This project's prompt engineering workflow is split into several files. They are designed to be read in the following order to understand the full process from planning to execution:

1. **Strategy (This Notebook)**: This file outlines the high-level plan, key decisions (like model and book selection), cost analysis, and quality standards for the entire question generation phase.
2. **[Experimentation](03-1_prompt_eng_experimentation.ipynb)**: It documents the iterative process of developing, testing, and validating the master prompt for the three question types Explanatory (EX), Multiple-Choice (MCQ), and Factual-Recall (FR). It also documents the development and testing of the full automated script for making the API calls.
3. **[Execution of the question generation script](03-2_data_generation.ipynb)**: The finalized prompts and automated Python script are used to run the full, large-scale generation process over the selected source texts (Books 3, 4, and 7).
4. **[Validation and merging](03-3_create_baseline_v2.ipynb)**: The raw, generated questions are compiled, put through a final validation and de-duplication pipeline, and then merged with the baseline dataset to create the new, balanced v2 dataset for the next project phase.

### Scope of the notebook

This notebook focuses on using a Large Language Model (LLM) to generate a new, balanced set of questions. The notebook defines the prompt engineering strategy.It outlines the key decisions, scope, constraints, and overall approach to consider when generating the new questions.

>"I utilized an Iterative Layering Strategy. Instead of architecting a brittle, complex system from scratch, I established a functional baseline (Manual API calls) to validate the 'physics' of the LLM. Once validated, I progressively layered on infrastructure (Prefect) and logic (SBERT) to ensure the foundation remained stable at every complexity jump."
>I built a simple script that worked, then wrapped it in automation (experimentation), then I wrapped that in orchestration (prefect pipelin)

# Table of Contents

1. [**Introduction**](#1-introduction)
2. [**Glossary of key terms**](#2-glossary-of-key-terms)
3. [**Scope, limits, and constraints**](#3-scope-limits-and-constraints)
4. [**Key decisions**](#41-key-decisions)<br>
    4.1. [Overview of decisions](#41-overview-of-decisionss)<br>
    4.2. [Decision 1: Source content](#42-decision-1---source-content)<br>
    4.3. [Decision 2: Number of questions](#43-decision-2---number-of-questions)<br>
    4.4. [Decision 3: Selection of the LLM model API provider](#44-decision-3---selection-of-llm-model-api-provider)<br>
5. [**Approach**](#5-approach)<br>
    5.1. [Overall approach](#51-overall-approach)<br>
    5.2. [Potential duplicate questions with multi-runs](#52-potential-duplicate-questions-with-multi-runs)<br>
    5.3. [Master prompt](#6-master-prompt)<br>
    5.4. [Source text preparation](#7-source-text-preparation)<br>
    5.5. [Script for generating questions](#8-script-for-generating-questions) 

# 2: Glossary of key terms

To ensure clarity and consistency, the following terms are defined within the context of this analysis:

|Term | Abbreviation | Description|
|-|-|-|
|Natural Language Processing|NLP|A field of AI that enables computers to understand, analyze, and generate human-language|
|Large Language Model|LLM| A type of AI model trained on large amounts of text to understand, generate, and analyze human language|
|Factual Recall (Question) | FR | Question seeking specific objective info (name, date, place, etc.). Identified by keywords such as 'What', 'Who', etc. |
| Explanatory|EX| Question seeking explanation, opinion, or procedure, often identified by keywords like 'Why' or 'How'.|
| Multiple-Choice Question| MCQ| A question that provides options for answers to select from|
| MVP of game| CLI-MVP | The first phase prototype of the Harry Potter Trivia game (Command Line Interface - Minimum Viable Product) |

Instead of jumping right into testing and prompting, we need to develop a high-level strategy to think out the steps and ensure the API calls are efficient, within budget, and deliver high-quality results. This section outlines the scope, key decisions, and overall approach for this task.

## 3: Scope, limits, and constraints

In the EDA and processing stage of the baseline dataset, replacements for problematic questions were developed using LLM models. Lessons learned from this initial stage have informed the following criteria for question generation: 

1. **Budget**: The limit to API expenditure is set to $25.00 CAD.

2. **Quality standard**: the generated questions must be:
    - *Factually accurate*: Verifiable against the source text.
    - *Lore-based and within scope*: sourced exclusively from the canon of the specified books.
    - *Formatted properly*: The questions should match the question structures defined for the questions types, EX, MCQ, FR, YN, in the content and source guidelines for [standardizing dataset input](../02_eda_and_deduplication.ipynb).
    - *Non-leading*: phrased to test knowledge without hinting or directing towards the answer.
    - *Varied difficulty*: flag each question with an appropriate difficulty (Easy, Medium Hard).
    - *Sentence-BERT training data*: for the EX and FR types, the output must include 4 distinct, grammatically correct, semantically similar variations of the primary answer. These answers can then be used to train Sentence-BERT for answer checking.
    - *Quality over quantity*: Hard-coding a specific number for the model to extract from each model may push it to generate questions that might be of lower quality to meet the allocated quota in cases where the chapters are sparse. Instead, the model will have discretion to generate fewer questions from sparser chapters, prioritizing quality over a fixed quota.

# 4: Key decisions
A number of key decisions need to be considered and defined to ensure we achieve the desired criteria from [section 4.1](#41-scope-limits-and-constraints).

## 4.1: Overview of decisions

|Decision | Rational & key considerations |Outcome|
|-|-|-|
|Number of questions|The primary goal is to generate a diverse dataset with a strong focus on Explanatory (EX) and Factual-Recall (FR) questions for Sentence-BERT training. An initial high target was revised to prioritize quality over quantity. Also new FR and MCQ questions will help further balance the dataset |250~300 EX, 250~300 FR, ~150 MCQ|
|Source content| The selection is focused on a small number of books to ensure thematic range and a natural story arc progression (beginning, middle, end). Chosen books must be eventful, well-paced, and popular| Books 3,4,7|
|API provider & LLM models|An assessment of free tiers and pay-as-you-go pricing determined that the Google Gemini API is the most practical and cost-effective option for both development and bulk generation.| Google Gemini 2.5 (test between Flash and Pro)|

## 4.2: Decision 1 - Source content

To ensure questions are correct, lore-based, and reliable (i.e. minimize hallucinations) they need to be sourced directly from the books themselves. The questions will be sourced from book 3 (*Prisoner of Azkaban*), book 4 (*Goblet of Fire*), and book 7 (*The deathly hallows*). As some of the most popular books in the series [[1]](#7-references), they are likely to be well-known by players. They also represent a reasonable breadth of the saga's content and tone, progressing from the lighter mood of the early books to the darker themes of the finale. These novels are also relatively eventful and well paced through evenly across the chapters, which would make them good content for facts and events to centre questions around. In contrast, book 5 (*Order of the Phoenix*) for example, is mostly Harry's internal diaglogue unitl the final chapters of the book. 

If further content can be explored, book 6 (*The half-blood prince*) can also be considered. 

## 4.3: Decision 2 - Number of questions

The baseline dataset needs to be balanced with respect to question type and source content (refer to the [EDA notebook](../02_eda_and_deduplication.ipynb) for details). Currently, the baseline dataset is skewed heavily towards FR type questions, with EX and MCQ. These questions are also predominently from auxilliary sources such *Fantastic beasts and where to find them* and *Quidditch through the ages* which is less known then the main books. 

New questions will be added to address these gaps and to provide robust training data for the answer-checking model. The generation will target:

- **~250-300 EX questions**: This is the top priority, as these questions add the most semantic depth for player engagement and for training the Sentence-BERT answer checker. An initial target of 500 EX, 100 MCQ and 50 FR were considered primarily looking at balancing question type. But this would put mean generating 10 to 12 questions from a chapter. This might push the model to prioritize meeting the quota in sparser chapters, possibly introducing repetitive or lower-quality questions. It would be better to instead focus the prompts on generating a few (4 to 6) high quality explanatory question per chapter, resulting in about 200~250 questions. There is enough room in the budget to rerun the successful prompts to generate more questions from other books, as needed.

- **~250-300 FR questions**: A similar number of FR questions is needed to ensure the answer-checking model is robustly trained on both long-form semantic meaning (from EX answers) and short-form factual accuracy. The planned answer checker will first attempt a simple fuzzy match and if that fails it will fall back to a semantic similarity check. This makes the fine-tuned Sentence-BERT model a critical 'safety net' for factual answers. These questions also add diversity to the FR questions. In the [EDA](../02_eda_and_deduplication.ipynb), it was found that the existing FR question focus heavily on auxilliary content more than the main books.

-**~150 MCQ questions**: This will significantly increase the diversity of question types and improve the gameplay experience.

## 4.4: Decision 3 - Selection of LLM model API provider

The selection of an LLM provider was guided by a pragmatic assessment of available free tiers and pay-as-you-go pricing. While several state-of-the-art models were considered, the **Google Gemini API** quickly emerged as the most practical choice for this project's development and execution phases.

### A. Basis for estimate for API calls

- safety margin = 20%
- Input context: ~14,100 tokens. This is based on two chapters per API call with an mean / median word count of ~5300 per chapter [[2]](#7-references). As per OpenAI guidelines [[3]](#7-references), a general rule of thumb is to consider 100 tokens to be about 75 words. So each chapter would have about 7,049 tokens.
- Input prompt (cached): ~800 tokens. This would be the master prompts, including all instructions, few-shot examples, and formatting rules.
- Output json tokens: ~1800 tokens for explanatory questions (to generate 4~6 high-quality questions with 275~300 token per record). The questions and their answers will be wordier and also have multiple answers to train the Sentence-BERT for answer checking later. ~200~260 tokens for the FR and MCQ questions (to generate ~3 questions). We can an expect ~308 tokens for EX, ~163 for FR, and ~198 tokens for MCQ for one output question 
- Number of API calls required for all three question types: 
    - number of chapters: 22 (book 3) + 37 (book 4) + 37 (book 7) = 96 
    - number of calls per question type = 48
    - total number of API calls for EX, FR, MCQ: 144

So based on this we can establish the following cost parameters:
|**Total Input tokens (context)**| **Total input tokens cached (prompt)**| **Output tokens**|
|-|-|-|
|2.03 M| 0.115 M | 0.142 M|

### B. Free-tier access 
The most ideal approach would be to carry out the analysis within the free-tiers of the providers. This method will be used for testing and experimenting and will also be explored for the batch generation. 

Currently only Google offers a direct access free-tier. Open AI no longer does and DeepSeek requires a pre-paid credit ($5 minimum). DeepSeek can be accessed as a free-tier through third parties (e.g. OpenRouter, Nvidia NIM APIs) but that would require familiarizing with a new platform. As such Google API is the best way forawrd within this tier and an analysis shows this is feasible with several Gemini models:

|Provider|Model| Rate limit<br> (calls per min)|Rate limit <br> (calls per day)|Token limits <br> (per min)| Daily call limit (RPD)| Safe delay <br> times | **Estimated run <br> times** (144 calls)| Reference|
|-|-|-|-|-|-|-|-|-|
|Google | Gemini 2.0 Flash| 15 | 200 | 1,000,000| 200 |5s | **~12 mins**| [[4]](#7-references)| 
|Google | Gemini 2.5 Flash| 10 | 250| 250,000| 250 | 7s| **~17 mins** | [[4]](#7-references)| 
|Google | Gemini 2.5 Pro (flagship)| 2 | 50| 125,000|50|31s| **~25 mins** (over 3 days) |[[4]](#7-references)|

The cost determining factor between the all three rate limits is the **Rate Per Minute (RPM)**, which can be handled by adding a safe delay between API calls in the generation script. This can be illustrated by Looking at the most restrictive option (Gemini 2.5 pro). One API call will have ~15,000 tokens. With a RPM of 2, we would be sending a total of 30,000 tokens in a minute (36,000 with the safety margin). The token counts are below the 125,000 limit. The total calls we need to make are a 144, which would mean we can split the calls over three days since the daily limit is 50 calls (not necessary for the other two models).  If the testing determines that the EX atleast have to be generated with 2.5 Pro and the FR and MCQ are of sufficient quality for FR and MCQ. Dividing the questions between the two models would bring the run time to a day.

### C. Paid-tier
As a contingency, a cost estimate was prepared to ensure that even a fully paid run would remain within the $25 budget. 

|Provider| Model| Input text<br>(USD) | Cached input<br>(USD)| Output<br>(USD) | **Cost estimate<br>(USD(CAD))** | Reference|
|-|-|-|-|-|-|-|
|OpenAI| GPT-5| 1.25| 0.125 | 10.00 | **4.76** (**6.67**)|[[5]](#7-references)|
|Google| Gemini 2.5 Pro| 2.50| 0.625| 15.00| **8.72** (**12.21**)| [[6]](#7-references)|
|Google| Gemini 2.5 Flash|0.30| 0.075| 2.50| **1.17** (**1.63**)| [[7]](#7-references)|
|DeepSeek|Reasoner V3.2-Exp|  0.55| 0.14| 2.19| **1.73** (**2.42**)| [[8]](#7-references)|

All options are within budget and Gemini 2.5 Flash is the most cost-effective. It should be noted though that DeepSeek provides a reasoning model at almost the same cost as the Gemini Flash (and both less than a cup of coffee! :D).

### D. Final decision summary 

After the preliminary review of the free tiers and pricing models, a full, multi-provider comparison is unnecessary. The **Google Gemini API** stands out as the most practical and cost-effective option for experimenting and  bulk question generation:

- **Viable free-tier**: Both Gemini 2.5 Flash and Gemini 2.5 Pro offer generous free tiers with rate limits that are sufficient to generate the entire batch of new questions within a reasonable timeframe (one day for Flash, two for Pro).

- **A cost-effective paid option**: In the "worst-case" scenario where the quality of Gemini 2.5 Pro is deemed for all questions ( 12.21 CAD) or essential for EX types (4.75 CAD), the estimated pay-as-you-go cost for the entire generation process is well within the project's budget cap of $25.

- **Lower friction compared to alternatives**: OpenAI no longer offers a free-tier. A free-tier of DeepSeek is offered through other third parties (e.g. OpenRouter, Nvidia NIM APIs) but it would another level of learning and complexity to the workflow. To use DeepSeek directly requires pre-paid credits  (a minimum $5 balance), which is less suitable for a one-time, well-defined task.

# 5: Approach

The overall approach follows a standard machine learning workflow, namely prompt development, automated generation, and quality assurance. A key challenge identified was the risk of generating duplicate facts in different question types across the independent runs. To address this, a data-driven, adaptive approach will be used.

## 5.1: Overall approach

1. **Prompt development and testing**: Develop the structure of the prompts for a given question type (EX, MCQ, FR) that will deliver quality results that meet defined criteria. The testing and analysis can be done using the Google Gemini free-tier. **Outcome**: prompt structure, output file format, confirm number of questions to generate per chapter, error handling, batching strategy.

2. **Model selection**: with the optimized prompts determine which Gemini model balances quality and cost the best and select. **Outcome**: a defined model to proceed with.

3. **New question generation**: Use the selected model to generate questions with finalized prompts through API calls and a script. **Outcome**: dataset of new questions and answers to balance and diversify the *Baseline v1* dataset.

4. **Quality assurance**: 1. manual spot check (immediate) 2. Use the developed quality metric scores to get an overall quality score and identify outliers. Once satisfied then merge with baseline dataset (this needs embedding values and will be done with other phase 2 custom NER labels and embedding value comparison). **Outcome**: confirm that known problems such hallucinations and other errors not present. confirm question quality, overall prompt effictiveness. Approval to proceed - ie. merge new questions with baseline dataset.

## 5.2: Potential duplicate questions with multi-runs

Initially, the prompting approach was straightforward with multi-pass through the books for each question type (and is the basis for the cost estimate). Here, the source book chapters would be divided so that each API call would use 2 chapters. The prompt would loop through all the chapters with a master prompt for a specific question type (e.g EX) and generate new questions. New questions would be generated for each question type in a separate, independent run over the entire source text.

However, while considering the approach, a potential challenge emerged. Since the runs are independent and the LLM has no-memory or means of tracking between runs, there is a potential of duplication of the *core fact* from a given chapter. The model will likely pick the most prominent fact or trivia kernel from a given chapter, leading to redundant questions in different formats, for example:
- **FR run**: "Who is the Headmaster of Hogwarts?"
- **MCQ run**: "Which character is the Headmaster of Hogwarts? (Option 1), (Option 2), Dumbledore, (Option 4)."

Also, we will not be able to gauge the extent of duplicates until we have made the different question runs. 

### 5.2.1: Evaluating alternative approaches
To address this challenge proactively, several alternative strategies were considered and evaluated.

- **Discarded approach 1: two-stage kernel extraction**: here, a first prompt extracts key facts ("kernels") from the text, and a second prompt formats these kernels into different question types. This approach was rejected because it would be less efficient. It would require at least two API calls per question, increasing costs. More importantly, it would strip the rich narrative context from the generation process, resulting in lower-quality, generic questions.

- **Discarded approach 2: segregating books by question type**: Assign specific books to each question type (e.g., Books 4, 6, 7 for EX; Books 1, 2 for MCQ). This would logically guarantee zero overlap. This was also rejected because it would introduce another bias into the dataset. The dataset would be thematically skewed where, for example, EX questions would only cover late-series topics and MCQs would only cover early-series topics, creating a disjointed and predictable player experience.

- **Viable option-A: keep the multi-Pass approach with post-processing deduplication**: This keeps the approach simple and the question generation reliable, with each prompt is a focused expert. However this will require a robust post-processing de-duplication step after all the new questions have been generated. This could be done by leveraging the existing cutom method to remove near-duplicates from the EDA [notebook](../02_eda_and_deduplication.ipynb). We would need to replace the TF-IDF vectorizer since it will not have the vocabulary of the new questions and it more importantly, doesn't have the contextual semantic analysis necessary for comparison between different question formats. We could use a pre-trained Sentence-BERT model for similarity analysis and continue with the graph analysis for grouping.  

- **Viable option-B: a single-pass "super-prompt"**: This would be very efficient with the API calls (reducing them by ~66%). The model would have a holistic view of the task for each chapter chunk would inherently remove duplication. However, the single prompt would become a lot more complex and lengthy, requiring careful engineering and testing to ensure the model can handle the mixed-output request reliably. And the results might not be consistent across all the chapters.

### 5.2.2: Final hybrid approach to minimize duplication 

Instead of assuming the degree of duplication, we will adopt a data-driven, adaptive approach to determine the best path forward:

1. **First-pass**: Execute your full multi-pass plan (three separate runs for EX, FR, and MCQ) for **Book 3 only**. We can log actual input and output tokens per run with the script.

2. **Check-point**: A quick manual review and then an analysis with the refactored near-duplicate detection method to quantify the extent of duplication (count or percentage of new questions). We can use the averaged actual token logs to verify the cost estimate as well.

3. **Continue question generation**: The check point results would then determine which option to select, for example, if:
    - *Duplicates are low (<10% overlap)*: continue with option-A.  The probabilistic nature of the LLM is enough to ensure variety and the post-processing script will be sufficient to clean up the few duplicates. 
    - *Duplicates are high* The data will confirm a different approach to multi-pass is needed, move with option-B a book at a time and confirm results.

This will also make sure the API calls are cost-effective and efficient.

## 5.3: Guidelines for the Master prompt

Three prompt templates will be finalized for each question type, namely EX, FR, MCQ. Each prompt will be engineered to be a specialized "expert" for its task and include key features such as [[9]](#7-references):

- **Persona**: Instructs the LLM to act as an expert trivia creator.
- **Few-shot examples**: Provides high-quality examples of the desired output format.
- **Structured output**: Demands a response in a specific, valid JSON structure.
- **Source grounding**: Requires the LLM to base its answer only on the provided source text and to cite the specific quote.
- **Integrated Features**: Includes fields for difficulty and answer variations (for Sentence-BERT training) as required.

The prompt scripts locations: [EX prompt](../../scripts/prompts/explanatory_prompt.txt), [FR prompt](../../scripts/prompts/factual_recall_prompt.txt), and [MCQ prompt](../../scripts/prompts/mcq_prompt.txt). These can be combined and tested into a single-pass super-prompt [option-B, section 4.2](#442-potential-duplicate-questions-with-multi-runs) if needed.

## 5.4: Source text preparation 

1. The full digital corpus of all seven books was downloaded [[10]](#7-references) as an R package and converted for use in this notebook using a [script](../../scripts/extract_hp_corpus.py). 

2. The chapters were extract from the books of interests. A quick review was done to validate the content to make sure it was clean and suitable for use. The chapters were given systematic names, so that the prompts could loop through them.

## 5.5: Script for generating questions
A Python script ([generate_questions.py]()) will be developed to automate the generation process. Its core functionality will include:

- Loading a specified prompt template from the prompts/ directory.
- Looping through all chapter files within the chapters/ directory.
- Dynamically inserting the chapter text and other parameters (like the number of questions) into the prompt template.
- Managing the API calls to the selected LLM, including handling authentication and potential errors.
- Receiving the JSON response from the API, validating its structure, and appending it to a final output file (e.g., generated_questions.jsonl).

# 6: References

1. “Best Harry Potter Books (List 1509),” Goodreads Listopia, [Online]. Available: https://www.goodreads.com/list/show/1509.Best_Harry_Potter_Books. [Accessed: Oct. 3, 2025].
2. M. Siebel, “Harry Potter and the Text Analysis,” RPubs by RStudio, [Online]. Available: https://rpubs.com/siebelm/harry_potter. [Accessed: Oct. 3, 2025].
3. “What are tokens and how to count them,” OpenAI Help Center, [Online]. Available: https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them. [Accessed: Oct. 2, 2025].
4. Google, “Rate limits – Gemini API (Free Tier),” Google AI for Developers, [Online]. Available: https://ai.google.dev/gemini-api/docs/rate-limits#free-tier. [Accessed: Nov. 2, 2025].
5. OpenAI, “Pricing” OpenAI Platform Documentation, [Online]. Available: https://platform.openai.com/docs/pricing. [Accessed: Oct. 2, 2025].
6. Google, “Gemini Developer API Pricing – Standard,” Google AI Developers: Gemini API Documentation, [Online]. Available: https://ai.google.dev/gemini-api/docs/pricing#standard_9. [Accessed: Oct. 2, 2025].
7. DeepSeek, “Model Details,” DeepSeek API Pricing, [Online]. Available: https://api-docs.deepseek.com/quick_start/pricing#model-details. [Accessed: Oct. 2, 2025].
8. OpenAI Help Center, “Best practices for prompt engineering with the OpenAI API,” Aug. 2025. [Online]. Available: https://help.openai.com/en/articles/6654000-best-practices-for-prompt-engineering-with-the-openai-api. [Accessed: Oct. 5, 2025].
9. Google Cloud, “What is prompt engineering?,” [Online]. Available: https://cloud.google.com/discover/what-is-prompt-engineering?hl=en. [Accessed: Oct. 5, 2025].