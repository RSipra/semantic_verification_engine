# Data Directory 

* **01_raw**: Original, immutable data dumps.
* **02_intermediate**: Data in the middle of processing. Contains files such as temporary CSVs, parquets, and cleaning artifacts.
* **03_models**: Saved model weights (e.g., planned fine-tuned SBERT and student model adapters).
* **04_metrics**: Evaluation reports, drift analysis logs, and quality scorecards.
* **05_final**: he "Gold Standard" production database. This is the dataset loaded by the Game Engine.
* **06_books**: The parsed, chapter-segmented Harry Potter corpus (Source of Truth). 
* **07_pipeline_logs**: **Traceability Layer.**
    * `manifests/`: "Flight Plans" (JSON configurations saved before a run starts).
    * `runs/`: "Receipts" (JSON summaries saved after a run finishes).
    * `logs/`: Raw console output logs from Prefect.
* **08_generated_questions**: Raw JSONL output from the Gemini Generation Pipeline.
* **09_themes**: Curated collections of text excerpts for cross-book thematic generation (e.g., "Dobby's arc").

## 📂 Data management

This project follows MLOps best practices by strictly decoupling **Code** (Git) from **Data** (DVC). As a result, the `data/` directory in this repository serves as a skeleton.

* **No copyrighted material:** The source text for the Harry Potter novels is **not included**. To run the generation pipeline, you must provide your own text files in `data/06_books/`.
* **No heavy artifacts:** Large datasets (JSONL), embeddings, and models are tracked via **DVC** (Data Version Control) and stored in a private remote storage bucket.
* **Full observability:** While the raw data is excluded, the **Pipeline Logs** (`data/07_pipeline_logs/`) are fully committed. You can audit the history of every run (Manifests, Configs, Token Usage) without needing the data itself.

### 🔄 How to "rehydrate" the project
To get the `generate_question` pipeline running locally:

1.  **Add Source Data:** Place your text files in `data/06_books/` following the naming convention `book_chapter_N.txt`.
2.  **Run the Pipeline:** Execute `python scripts/generate_questions.py` to regenerate the datasets from scratch.
3.  **Result:** The `data/08_generated/` and `data/05_final/` folders will be populated by your local run.

