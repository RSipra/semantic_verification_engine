graph TD
    subgraph Phase 1: Existing Baseline Setup
        A[Raw Trivia Data v0] --> B[Data Cleaning & Feature Engineering Notebook]
        B --> C[Baseline Dataset v1.0.0.csv]
        C --> D[TFIDF Vectorizer v1.0.0.pkl]
    end

    subgraph Phase 2: New Question Generation & QA
        E[Master Prompt - from prompt_engineering.ipynb] --> F[LLM API Call Script]
        F --> G[Raw New Questions.csv]

        G --> H[QA & Scoring Pipeline]
        H --> I[NER Gazetteers]
        H --> D
        H --> J[Sentence-BERT Model]

        H --> K[New Questions w/ Scores.csv & QA Report]
        K --> L[Manual Review & Approval]
        L --> M[Approved New Questions.csv]
    end

    subgraph Phase 3: Integration & Finalization
        M --> N[Data Ingestion Pipeline]
        C --> N
        N --> O[Updated Dataset v2.0.0.csv]

        O --> P[Retrain TFIDF Vectorizer]
        P --> Q[TFIDF Vectorizer v2.0.0.pkl]

        O --> R[Run Final Analysis & Status Dashboard]
        R --> S[Analysis & Report - final_analysis.ipynb]
    end

    subgraph Phase 4: Gameplay & Future Work
        O --> T[Gameplay Engine]
        Q --> T
        J --> T
        T --> U[Player Experience]
    end

    style A fill:#D0F0C0,stroke:#333,stroke-width:2px
    style C fill:#D0F0C0,stroke:#333,stroke-width:2px
    style D fill:#ADD8E6,stroke:#333,stroke-width:2px
    style G fill:#F0E68C,stroke:#333,stroke-width:2px
    style K fill:#F0E68C,stroke:#333,stroke-width:2px
    style M fill:#D0F0C0,stroke:#333,stroke-width:2px
    style O fill:#D0F0C0,stroke:#333,stroke-width:2px
    style Q fill:#ADD8E6,stroke:#333,stroke-width:2px
