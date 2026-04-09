"""
Project: SVE (ref implementation: Harry Potter Trivia)
PHASE 2 Tracer -> Context Refinery: Add descriptive features
"""
from collections import OrderedDict, Counter
from typing import Optional
import re
from IPython.display import display
from IPython.core.display import Markdown
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import pandas as pd

# Import custom methods from project scripts
from ds_utils import ds_constants as const

## 1. Length Metrics

# FROM P1 eda_scripts: Helper function that returns a Series of the word counts for a
# column of interest (e.g. 'question' or 'answer')
def get_clean_word_counts(dataframe: pd.DataFrame, column_name: str) -> pd.Series:
    """
    Returns a Series with the number of clean words (ignoring punctuation) in each entry.
    
    :parame dataframe: the data frame on which to perform the search on.
    :type dataframe: pd.DataFrame
    :param column_name: the column name for which to count words in (e.g. `question` or `answer`)
    :type column_name: str
    
    :return: A Series with the word counts for each entry in the specified column.
    :rtype: pd.Series[int]
    
    """
    return dataframe[column_name].apply(lambda x: len(re.findall(r'\b\w+\b', x)) if pd.notnull(x) else 0)

# FROM P1 eda_scripts: Helper function to classify answer types using a hierarchical, rule-based approach
def classify_answer_type(row):
    """
    Classifies an answer into 'text', 'date', 'year', or 'numeric' using a
    robust, hierarchical rule-based approach.
    """
    answer_str = str(row['answer']).strip()
    answer_lower = answer_str.lower()

    # Rule 1: Check for dates (UPDATED LOGIC)
    # Split the answer into a set of words to check for whole-word matches.
    words_in_answer = set(re.split(r'\W+', answer_lower))
    contains_month = words_in_answer.intersection(const.MONTH_NAMES)
    
    contains_digits = any(char.isdigit() for char in answer_str)

    if contains_month and contains_digits:
        return 'date'
    try:
        if '-' in answer_str and pd.to_datetime(answer_str) is not pd.NaT:
            return 'date'
    except (ValueError, TypeError):
        pass

    # Rule 2: Check for year patterns
    is_historical_year = re.fullmatch(r'\d{1,4}\s*(BC|AD)', answer_str, re.IGNORECASE)
    is_standalone_year = re.fullmatch(r'\d{4}', answer_str)
    is_century = re.search(r'\b\d{1,2}(st|nd|rd|th)\s+century\b', answer_lower)
    if is_historical_year or is_standalone_year or is_century:
        return 'year'

    # Rule 3: Check for numeric (now runs on all inputs)
    cleaned_for_num = re.sub(r'[^\d\.]', '', answer_str) # Keep digits and decimal points
    if cleaned_for_num:
        try:
            float(cleaned_for_num)
            letters = sum(c.isalpha() for c in answer_str)
            if letters == 0: # If there are no letters, it's numeric
                return 'numeric'
        except (ValueError, TypeError):
            pass

    # Rule 4: If all else fails, it's text
    return 'text'


# FROM P1 eda_scripts: create three columns with token lists from questions, answers, 
# and combined (question, answer) in the datagrame respectively
def create_token_columns(dataframe: pd.DataFrame, tokenizer) -> pd.DataFrame:
    """
    Adds tokenized columns for questions and answers to the DataFrame.

    This function applies a provided tokenizer to the 'question' and 'answer'
    columns, creating new columns with lists of unique tokens where the order
    of first appearance is preserved. It also adds a column with the
    combined tokens from both.

    Note: This function modifies the input DataFrame directly (in place) by
    adding new columns, and also returns the modified DataFrame.

    :param dataframe: The input pandas DataFrame. Must contain 'question'
                      and 'answer' columns with string data.
    :type dataframe: pd.DataFrame
    :param tokenizer: A function that takes a string as input and returns
                      a list of token strings.
    :type tokenizer: Callable[[str], List[str]]
    :return: The modified DataFrame with 'question tokens', 'answer tokens',
             and 'combined tokens' columns added.
    :rtype: pd.DataFrame
    """
    # Create unique 'keywords' column by tokenizing 'question' and 'answer',
    # excluding unwanted words - keep the same order 
    dataframe['question_tokens'] = dataframe.apply(
        lambda row: list(OrderedDict.fromkeys(tokenizer(row['question']))), axis=1)
    dataframe['answer_tokens'] = dataframe.apply(
        lambda row: list(OrderedDict.fromkeys(tokenizer(row['answer']))), axis=1)
    dataframe['combined_tokens'] = dataframe.apply(
        lambda row: row['question_tokens']+ row['answer_tokens'], axis=1)
    
    # Create the final column of unique combined tokens, preserving order
    dataframe['combined_unique_tokens'] = dataframe['combined_tokens'].apply(
                    lambda x: list(OrderedDict.fromkeys(x)) if isinstance(x, list) else [])
    
    # Drop the intermediate 'combined tokens' column as it's no longer needed
    dataframe.drop(columns=['combined_tokens'], inplace=True)
    
    return dataframe

# Refactored from P1 eda_scripts.py (get_main_keyword)
def extract_main_keyword(token_list: list) -> str:
    """
    Extracts a primary keyword based on Priority levels, 
    preserving the exact left-to-right order of the original sentence.
    """
    # guard against empty lists or NaNs
    if not isinstance(token_list, list) or len(token_list) == 0:
        return 'unassigned'

    # First pass: Scan left-to-right for Priority 1 keywords (e.g., 'how', 'why')
    for keyword in token_list:
        if keyword in const.PRIORITY_1_KEYWORDS:
            return keyword 

    # Second pass: Scan left-to-right for Priority 2 keywords (e.g., 'who', 'what')
    for keyword in token_list:
        if keyword in const.PRIORITY_2_KEYWORDS:
            return keyword 

    # Fallback: If no priority words exist, return the very first token in the sentence
    return token_list[0]

# Refactored from P1 eda_scripts.py
def get_top_keywords(series_of_keyword_lists: pd.Series, top_n: int = 3, exclude_list=None) -> str:
    """
    Flattens a series of token lists, counts frequencies using Python's 
    highly-optimized Counter, and returns a formatted string of the top N keywords.
    """
    if exclude_list is None:
        exclude_list = set()
    else:
        exclude_list = set(exclude_list)

    # 1. Flatten the lists and filter in one lightning-fast pass
    all_tokens = [
        token for sublist in series_of_keyword_lists 
        if isinstance(sublist, list) # Safety check
        for token in sublist 
        if token not in exclude_list
    ]

    if not all_tokens:
        return "None"
  
    # 2. Use Counter to find the top N instantly (bypassing Pandas overhead)
    top_counts = Counter(all_tokens).most_common(top_n)

    # 3. Format into your required string: "keyword1 (count1), keyword2 (count2)"
    return ", ".join([f"{keyword} ({count})" for keyword, count in top_counts])

def generate_coverage_table(df: pd.DataFrame):
    """
    Generates a hierarchical coverage table showing Book-level macro stats 
    and Chapter-level micro stats.
    """
    # 1. Safely extract Book and Chapter (Assuming format: "Book Title, Chapter X")
    df['Book'] = df['source_reference'].apply(lambda x: str(x).split(',')[0].strip() if pd.notna(x) and ',' in str(x) else 'Unknown')
    df['Chapter'] = df['source_reference'].apply(lambda x: str(x).split(',')[1].strip() if pd.notna(x) and ',' in str(x) else 'Unknown')

    # 2. Build the aggregations
    coverage_df = df.groupby('Book', observed=False).agg(
        Total_Questions=('question', 'count'),
        Chapters_Ingested=('Chapter', 'nunique') # How wide is our coverage?
    )

    # 3. Calculate the "Heaviest" Chapters (Top 2 most common chapters per book)
    coverage_df['Heaviest Chapters (Count)'] = df.groupby('Book', observed=False)['Chapter'].apply(
        lambda s: ", ".join([f"{chap} ({ct})" for chap, ct in s.value_counts().nlargest(2).items() if chap != 'Unknown'])
    )

    # 4. Clean up and display
    coverage_df = coverage_df.sort_values(by='Total_Questions', ascending=False)

# Refactored from P1 eda_scripts.py: status report generator for production dataset
def generate_dataset_status_report(input_dataframe: pd.DataFrame, 
                                   initial_total: Optional[int] = None) -> None:
    """
    Generates and displays a comprehensive status report ("Dashboard") for the trivia dataset.
    """
    # 1. Validate FIRST, no copying needed to save memory
    if not isinstance(input_dataframe, pd.DataFrame) or input_dataframe.empty:
        print("Cannot generate report: Input is not a valid or non-empty DataFrame.")
        return

    # --- Component 1: High-Level Metrics ---
    display(Markdown("## 📊 Trivia Dataset Status Map"))
    display(Markdown("---"))

    total_questions_final = len(input_dataframe)
    display(Markdown("### 1. Key Metrics"))

    metrics_text = (f"**- Total Unique Questions:** {total_questions_final}<br>")
    if initial_total is not None:
        net_change = total_questions_final - initial_total
        metrics_text += f"**- Net Change in Questions:** {net_change:+.0f}<br>"
        metrics_text += "   *(Note: Positive indicates added; negative indicates removed.)*<br>"

    if 'answer_type' in input_dataframe.columns:
        summary_line = ", ".join(
            [f"{atype} ({count})" for atype, count in input_dataframe['answer_type'].value_counts().items()])
        metrics_text += f"**- Answer Type Distribution:** {summary_line}<br>"

    display(Markdown(metrics_text))

    # --- Component 2: Main Summary Table ---
    display(Markdown("\n### 2. Breakdown by Question Type"))

    def count_uncategorized(series):
        return (series == 'unassigned').sum()

    aggregations = {
        'question': ('question', 'size'),          
        'answer': ('answer', 'nunique'),          
        'question_length': ('question_length', 'median'), 
        'answer_length': ('answer_length', 'median'),     
        'main_keyword': ('main_keyword', count_uncategorized) 
    }

    status_map_df = input_dataframe.groupby('question_type', observed=False).agg(**aggregations)

    top_main_keywords = input_dataframe.groupby('question_type', observed=False)['main_keyword'].apply(
        lambda s: ", ".join([f"{kw} ({ct})" for kw, ct in s.value_counts().nlargest(3).items() if kw != 'unassigned'])
    )

    top_answer_keywords = input_dataframe.groupby('question_type', observed=False)['answer_tokens'].apply(
        lambda s: get_top_keywords(s, top_n=3, exclude_list=const.INTERROGATIVE_KEYWORDS_LIST)
    )

    status_map_df = status_map_df.merge(
        top_main_keywords.rename('Top main_keyword'), left_index=True, right_index=True)
    status_map_df = status_map_df.merge(
        top_answer_keywords.rename('Top Answer Keywords'), left_index=True, right_index=True)

    status_map_df['Percentage (%)'] = (status_map_df['question'] / total_questions_final * 100)

    status_map_df = status_map_df.rename(columns={
        'question': 'Question Count',
        'answer': 'Unique Answer Count',
        'question_length': 'Median Q Len',
        'answer_length': 'Median A Len',
        'main_keyword': 'Unassigned Keyword Count' 
    })

    final_columns = [
        'Question Count', 'Percentage (%)', 'Unique Answer Count',
        'Median Q Len', 'Median A Len', 'Top Answer Keywords',
        'Top main_keyword', 'Unassigned Keyword Count'
    ]

    status_map_df = status_map_df[[col for col in final_columns if col in status_map_df.columns]]
    status_map_df = status_map_df.sort_values(by='Question Count', ascending=False)
    status_map_df.index.name = 'Question Type'

    display(status_map_df.style.format(
        {'Percentage (%)': '{:.1f}%', 'Median Q Len': '{:.1f}', 'Median A Len': '{:.1f}'}))
    print("\nNote: FR (Factual Recall), EX (Explanatory), YN (Yes/No or True/False), MCQ (Multiple Choice)")

    # --- Component 3: Visualizations ---
    display(Markdown("\n### 3. Visualizations by Question Type"))

    category_order = status_map_df.index.tolist()
    colors = sns.color_palette('Purples_r', n_colors=len(category_order))
    color_map = dict(zip(category_order, colors))

    # FIX 1: Reverted to 1x2 grid so axes[0] and axes[1] work correctly
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # FIX 2: Removed duplicate grouping block
    stacked_data = input_dataframe.groupby(['question_type', 'question_source']).size().unstack(fill_value=0)
    stacked_data = stacked_data.reindex(category_order)

    stacked_data.plot(
        kind='bar',
        stacked=True,
        ax=axes[0],
        color=['#5c3a92', '#b491c8'], 
        edgecolor='white',
        linewidth=1
    )

    for container in axes[0].containers:
        axes[0].bar_label(
            container, 
            label_type='center', 
            color='white', 
            fontsize=10, 
            fontweight='bold',
            fmt=lambda x: f'{x:.0f}' if x > 0 else '' 
        )

    axes[0].set_title('Question Types: Legacy vs. Synthetic Split')
    axes[0].set_xlabel('Question Type')
    axes[0].set_ylabel('Number of Questions')
    axes[0].tick_params(axis='x', rotation=0)
    
    max_bar_height = stacked_data.sum(axis=1).max()
    axes[0].set_ylim(0, max_bar_height * 1.15)
    axes[0].legend(title='Data Source', loc='upper right', framealpha=0.9)

    sns.boxplot(
        data=input_dataframe, x='question_type', y='answer_length',
        hue='question_type', palette=color_map, order=category_order,
        ax=axes[1], legend=False
    )
    axes[1].set_title('Answer Length Distribution by Question Type')
    axes[1].set_xlabel('Question Type')
    axes[1].set_ylabel('Answer Length (Words)')
    
    plt.tight_layout(rect=(0, 0, 1, 0.96))
    plt.show() # Display charts before the coverage table

    # FIX 3: Actually generate the coverage_df before trying to display it
    if 'source_reference' in input_dataframe.columns and 'question_source' in input_dataframe.columns:
        display(Markdown("\n### 📚 Source Text Ingestion Map"))
        
        temp_df = input_dataframe.copy()
        
        def parse_reference(row, part):
            source = str(row.get('question_source', '')).strip().lower()
            ref = row.get('source_reference', '')
            
            # 1. Expected Nulls: Legacy Data
            if source == 'legacy':
                return 'Legacy Data' if part == 'book' else 'N/A'
                
            # 2. Valid Synthetic Data
            if pd.notna(ref) and isinstance(ref, str) and ' ' in ref:
                splits = ref.split(' ', 1)
                return splits[0].strip() if part == 'book' else splits[1].strip()
                
            # 3. Unexpected Nulls: True Errors
            return 'Unknown (Missing)'

        # Apply the row-aware logic
        temp_df['Book'] = temp_df.apply(lambda row: parse_reference(row, 'book'), axis=1)
        temp_df['Chapter'] = temp_df.apply(lambda row: parse_reference(row, 'chapter'), axis=1)
        
        # Build the hierarchical aggregations
        coverage_df = temp_df.groupby('Book', observed=False).agg(
            Total_Questions=('question', 'count'),
            Chapters_Ingested=('Chapter', lambda x: x[~x.isin(['N/A', 'Unknown (Missing)'])].nunique())
        )
        
        # Calculate the "Heaviest" Chapters (ignoring N/A and Errors)
        coverage_df['Heaviest Chapters (Count)'] = temp_df.groupby('Book', observed=False)['Chapter'].apply(
            lambda s: ", ".join([
                f"{chap} ({ct})" for chap, ct in s.value_counts().nlargest(2).items() 
                if chap not in ['N/A', 'Unknown (Missing)']
            ])
        )
        
        coverage_df = coverage_df.sort_values(by='Total_Questions', ascending=False)
        display(coverage_df.style.background_gradient(subset=['Total_Questions'], cmap='Purples'))

    display(Markdown("\n---"))
    