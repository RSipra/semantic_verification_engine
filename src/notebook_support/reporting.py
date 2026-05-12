"""
Script for creating static dashboard reports on Master Dataset. Part of the ACES.
Can visualize volume, distribution, drift, and quality metrics. updates over time.
reporpused from Phase 1 logic.
"""

import datetime
import pandas as pd

def generate_dataset_health_report(df: pd.DataFrame, prev_df: pd.DataFrame | None) -> str:
    """
    Repurposed Phase 1 Logic: Generates a Markdown summary of the dataset.
    Tracks volume, distribution, and drift.
    WIP!
    """
    # 1. Calculate Stats (Reuse your Phase 1 math)
    total_q = len(df)
    type_counts = df['question_type'].value_counts().to_markdown()
    
    # 2. Compare with Previous (The "Drift" Monitor)
    growth = f"+{len(df) - len(prev_df)}" if prev_df is not None else "N/A"
    
    # 3. Generate Markdown
    report = f"""
# 📊 ACES Dataset Health Report
**Total Questions:** {total_q} ({growth})
**Last Updated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. Distribution by Type
{type_counts}

## 2. Quality Metrics
* **Missing Sources:** 
* **Duplicate questions:** 
"""
    return report