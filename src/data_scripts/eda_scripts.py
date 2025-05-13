"""
==================================================================
HARRY POTTER TRIVA GAME 
==================================================================

EDA Helper Functions for Harry Potter Trivia Analysis

This module provides a collection of reusable functions designed to perform
Exploratory Data Analysis (EDA) focused on keyword-based analysis of
question and answer data from the trivia dataset. Key analyses include
calculating descriptive statistics for text lengths and examining the
correlation between question and answer lengths for various question types.

Core Architecture & Workflow:
-----------------------------
The functions follow a Separation of Concerns pattern to enhance clarity,
reusability, and maintainability:

A.  **Low-Level Helper Functions:** Perform specific, isolated tasks such as:
A.1. Data Preparation Helpers    
    * Filtering data by keyword (`filter_df_by_keyword`)
    * Calculating word counts (`get_clean_word_counts`)
A.2. Calculation Helpers
    * Calculating descriptive stats (`get_len_descriptive_stats`)
    * Calculating Pearson correlation (`calculate_correlation`)
    * Categorizing correlation strength (`get_correlation_strength`)
    * Generating interpretation strings (`interpret_correlation`)
A.3. Plotting and Formatting Helpers
    * Creating specific plots (`create_correlation_scatterplot`, `create_ans_len_boxplot`)
    * Formatting tables (`format_descriptive_stats_table`)

B.  **Analysis Orchestration Functions:**
    "Manager" Function (`calculate_all_keyword_metrics`):**
    * Orchestrates the analysis workflow for a single keyword.
    * Calls the necessary low-level helpers for filtering and calculation.
    * Performs validation checks (e.g., sufficient data for correlation).
    * Returns a comprehensive 'results package' (dictionary). This package includes:
+       - 'keyword_for_display' (str): The input keyword, passed through for consistent
            use in display function titles/labels.
+       - 'metrics_for_summary' (dict): A dictionary of all calculated metrics (count, 
            stats, correlation info, etc.). This sub-dictionary does **not** internally 
            duplicate the keyword, making it clean for aggregation into summary tables.
+       - 'filtered_data_df' (pd.DataFrame): The actual DataFrame filtered by the input keyword.
+       - 'q_lengths_series' (pd.Series): Question lengths for the filtered data.
+       - 'a_lengths_series' (pd.Series): Answer lengths for the filtered data.
+   * This function does NOT perform any display actions itself.
    "Aggregate" Function (`create_comprehensive_summary_df`- Usually called from Notebook):**
    * Takes in a list of questions keywords to generate summary for. 
    * Takes in a list of keywords that are considered 'factual-recall' type.
    * Takes in a dataframe to generate the summary from
    * Calls the 'Manager' function (`calculate_all_keyword_metrics`) for each keyword in the input list.
+   * It then takes the 'metrics_for_summary' dictionary from the manager's output package.
+   * Crucially, it adds a 'Keyword' column to these metrics using the keyword from its own 
        iteration loop, and also adds the 'Question Type' classification.
+   * Aggregates these enriched metrics dictionaries into a single summary pandas DataFrame.

C.  **"Display Orchestration and View Functions"
    Function (`display_keyword_analysis` - Usually called from Notebook):**
    * Takes the 'results package' (output of `calculate_all_keyword_metrics`) as input.
    * Handles all presentation: printing formatted statistics, interpretations,
        generating plots by calling plotting helpers, and displaying sample data.
    * It uses the 'keyword_for_display' from the package for titles and labels,
+       and 'metrics_for_summary', 'filtered_data_df', 'q_lengths_series',
+       'a_lengths_series' for displaying the respective content.

D.  **N-gram Utility Functions**
    Specific utilities that calculate and directly print N-gram phrases 
    * List common phrases in the questions (print_common_ngrams)
    * List question keyword-based N-gram analysis (print_keyword_ngrams)
        (combining calculation and display for convenience).
    * Determine obsure unique n-grams using TF-IDF (rank_ngrams_by_tfidf)
        as a preliminary measure of answer difficulty (in development)

How to Use:
-----------
The typical workflow involves:

I.  **For Detailed EDA per Keyword (in Notebook):**
    1.  Call `calculate_all_keyword_metrics(keyword, df)` to get the `results_package`.
    2.  Call `display_keyword_analysis(results_package)` to view the full standard report.
    3.  Call `print_keyword_ngrams(dataframe['question'], keyword)` to view common 
            phrases starting with the specific `keyword` across all questions, potentially 
            varying n-gram ranges or stop words. This method uses the raw question column 
            from the dataframe (not the filtered_df).

II. **For Generating Summary Tables (in Notebook):**
    1. Create a list of question keywords to include in the summary_df
    2. Create a second (sublist) list from the keywords list that will be considered
        'factual-recall' type.
    3. Call `create_comprehensive_summary_df(question_keyword_list, factual_keywords_list, df)`
    4. Display the results:
        * direcly print the summary_df
        * or use the helper functions `display_correlation_summary()`, `display_status_map()`

See individual function docstrings for detailed parameter and return information.

"""

# Import necessary libraries

import re
from typing import List, Any, Union, Optional # For Python < 3.10
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator
from matplotlib.axes import Axes
from IPython.display import display
from IPython.core.display import Markdown
from scipy import stats
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer



#=============================#
##  A. HELPER FUNCTIONS       #
#=============================#

## A.1. Data Preparation Helpers
#------------------------------#

# Helper function to filter dataframe based on keyword
def filter_df_by_keyword(dataframe: pd.DataFrame, question_keyword: 'str') -> pd.DataFrame:
    '''
    This function filters for questions in the dataset based on a search of the provided `question_keyword` parameter.

    :parame dataframe: the data frame on which to perform the search on. The dataframe MUST have a column with a
    list of tokens generated from the question and the column is called `question keywords`
    :type dataframe: pd.DataFrame
    
    :param question_keyword: the search word to look for in the token lists within the `question keywords` column
    :type question_keyword: str
    
    :return: The filtered dataframe if matches are found (empty if none are found)
    :rtype: pd.DataFrame
    '''
    # Filter main dataframe
    filter_kw_questions = dataframe.loc[dataframe['question keywords'].apply(lambda x: question_keyword in x)]
    return filter_kw_questions

# Helper function that returns a Series of the word counts for a column of interest (e.g. 'question' or 'answer') 
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

## A.2. Calculation Helpers
#-------------------------#

# Helper function to get the descriptive statistics for a question keyword
def get_len_descriptive_stats(question_keyword: str, question_lengths: pd.Series, answer_lengths: pd.Series) -> dict[str, Any]:
    # pylint: disable=unsubscriptable-object
    """
    Calculates and returns comprehensive descriptive statistics for Q&A lengths.

    Computes count, mean, median, standard deviation, min, max, quartiles,
    interquartile range (IQR), range (max-min), and skewness for the provided
    Series of question lengths and answer lengths.

    Assumption: This function assumes the input Series (`question_lengths`, `answer_lengths`)
    are valid, non-empty, and have the same length. Input validation should
    be performed by the calling function.
c
    :param question_lengths: Series of (non-empty) numerical question lengths (typically derived from get_clean_word_counts).
    :type question_lengths: pd.Series[int]
    :param answer_lengths: Series of (non-empty) numerical answer lengths (typically derived from get_clean_word_counts).
    :type answer_lengths: pd.Series[int]
    
    :return: A dictionary with descriptive statistics for dataframe filtered by the `question_keyword`.
    :rtype: dict[str, Any]
    """
    # Calculate the basic descriptive statistics
    
    # For question lenghts
    q_count = question_lengths.count()
    q_mean = question_lengths.mean()
    q_std = question_lengths.std()
    q_min = question_lengths.min()
    q_max = question_lengths.max()
    q_median = question_lengths.median()
    q_25 = question_lengths.quantile(0.25)
    q_75 = question_lengths.quantile(0.75)
    q_iqr = q_75 - q_25
    q_range = q_max - q_min
    q_skew = question_lengths.skew()
    
    # For anaswer lengths
    a_count = answer_lengths.count()
    a_mean = answer_lengths.mean()
    a_std = answer_lengths.std()
    a_min = answer_lengths.min()
    a_max = answer_lengths.max()
    a_median = answer_lengths.median()
    a_25 = answer_lengths.quantile(0.25)
    a_75 = answer_lengths.quantile(0.75)
    a_iqr = a_75 - a_25
    a_range = a_max - a_min
    a_skew = answer_lengths.skew()
    
    # Create a dictionary to hold the results:
    
    descriptive_stats = {
        'question_keyword': question_keyword,
        'question_count': q_count,
        'question_mean': q_mean,
        'question_std': q_std,
        'question_min': q_min,
        'question_max': q_max,
        'question_median': q_median,
        'question_25th_percentile': q_25,
        'question_75th_percentile': q_75,
        'question_iqr': q_iqr,
        'question_range': q_range,
        'question_skew': q_skew,
        'answer_count': a_count,
        'answer_mean': a_mean,
        'answer_std': a_std,
        'answer_min': a_min,
        'answer_max': a_max,
        'answer_median': a_median,
        'answer_25th_percentile': a_25,
        'answer_75th_percentile': a_75,
        'answer_iqr': a_iqr,
        'answer_range': a_range,
        'answer_skew': a_skew      
    }
    return descriptive_stats       
    
# Helper function to calculate the Pearson correlation coefficient and p-value
def calculate_correlation(question_lengths: pd.Series, answer_lengths: pd.Series) -> tuple[float, float]:
    # pylint: disable=unsubscriptable-object
    """
    Calculates Pearson correlation coefficient r and p-value between the question and answer length provided. Validation that 
    the correct combination of question and answer lengths are provided is done in the calling function.

    :param question_lengths: Series of (non-empty) numerical question lengths (typically derived from get_clean_word_counts).
    :type question_lengths: pd.Series[int]
    :param answer_lengths: Series of (non-empty) numerical answer lengths (typically derived from get_clean_word_counts).
    :type answer_lengths: pd.Series[int]
    
    :return: A tuple containing the Pearson correlation coefficient (r) and the p-value (p).
    :rtype: tuple[float, float]
    """
    
    r, p = stats.pearsonr(question_lengths, answer_lengths)
    return r, p # type: ignore
# 
# Helper function to get the correlation strength based on the absolute value of r
def get_correlation_strength(r_value: float) -> str:
    """
    Categorizes the strength of a Pearson correlation coefficient (r). Typically the r-value is calculated  earlier by the `calculate_correlation` function

    :param r_value: The Pearson correlation coefficient.
    :type r_value: float
    
    :return: A string describing the strength ('Very Weak', 'Weak',
             'Moderate', 'Strong', 'Very Strong'), or 'Undefined' if input is NaN.
    :rtype: str
    """
    if pd.isna(r_value): # Handle NaN input
        return "Undefined" 
    abs_r = abs(r_value)
    if abs_r < 0.2:
        return "Very Weak"
    elif abs_r < 0.4:
        return "Weak"
    elif abs_r < 0.6:
        return "Moderate"
    elif abs_r < 0.8:
        return "Strong"
    else: # abs_r >= 0.8
        return "Very Strong"
    
## A.3. Plotting and Formatting Helpers:
#--------------------------------------#

# Helper function format the descriptive stats for quesiton and answer lengths in to a pretty table
def format_descriptive_stats_table(metrics_dict: dict[str, Any]) -> pd.DataFrame:
    """
    Format 

    :param metrics_dict: _description_
    :type metrics_dict: dict[str, Any]
    :return: A dataframe with descriptive statistics for question and answer lengths.
    :rtype: pd.DataFrame
    """
    # Display Descriptive Stats Table ---
    print("\nDescriptive Statistics for Question and Answer lengths (word count):")
    # Create DataFrame for side-by-side comparison
    stats_data = {
        'Question Length': {
            'Mean': metrics_dict.get('question_mean', np.nan),
            'Median': metrics_dict.get('question_median', np.nan),
            'Std Dev': metrics_dict.get('question_std', np.nan),
            'Min': metrics_dict.get('question_min', np.nan),
            'Max': metrics_dict.get('question_max', np.nan),
            'Skew': metrics_dict.get('question_skew', np.nan)
            # Add Quartiles/IQR/Range here if they are in metrics_dict and desired
        },
        'Answer Length': {
            'Mean': metrics_dict.get('answer_mean', np.nan),
            'Median': metrics_dict.get('answer_median', np.nan),
            'Std Dev': metrics_dict.get('answer_std', np.nan),
            'Min': metrics_dict.get('answer_min', np.nan),
            'Max': metrics_dict.get('answer_max', np.nan),
            'Skew': metrics_dict.get('answer_skew', np.nan)
            # Add Quartiles/IQR/Range here if they are in metrics_dict and desired
        }
    }
    stats_df = pd.DataFrame(stats_data)
    return stats_df.round(2) # Return the DataFrame for further use in display method

# Helper function to create the correlation scatterplot
def create_correlation_scatterplot(question_lengths: pd.Series,
                                   answer_lengths: pd.Series,
                                   question_keyword: str,
                                   ax: Union[Axes, None] = None) -> None:
    """
    Creates and displays a scatter plot with a regression line for Q&A lengths.
    If an Axes object is provided, plots onto that Axes. Otherwise, creates a new figure and Axes.
    
    :param question_lengths: Series of (non-empty) numerical question lengths (typically derived from get_clean_word_counts).
    :type question_lengths: pd.Series[int]
    :param answer_lengths: Series of (non-empty) numerical answer lengths (typically derived from get_clean_word_counts).
    :type answer_lengths: pd.Series[int]
    :param question_keyword: The keyword associated with this data subset.
    :type question_keyword: str
    :param ax: The matplotlib Axes object to plot on. In case of None, a standalone figure is created.
    :type ax: matplotlib.axes.Axes, optional
    """
    
    if ax is None:
        # If no axes provided, create new figure and axes for standalone plot
        fig, ax = plt.subplots(figsize=(10, 5))
        standalone_plot = True
    else:
        # Use the provided axes
        fig = ax.figure # Get the figure the axes belongs to
        standalone_plot = False
        
    print("\nScatter Plot with Regression Line:")
    # create the scatter plot with regression line
    sns.regplot(x=question_lengths, y=answer_lengths,
                scatter_kws={'color': 'purple', 'alpha': 0.5},
                line_kws={'color': 'black', 'linestyle': '--', 'linewidth': 1.5},
                ax=ax) # Use the determined ax object
    
    # Add title and labels
    title_str = f"Answer Length vs. Question Length ('{question_keyword.title()}')"
    ax.set_title(title_str)
    ax.set_xlabel("Question Word Count")
    ax.set_ylabel("Answer Word Count")
    ax.grid(True, alpha=0.3)
    
    # only when standalone_plot is True to display the plot
    if standalone_plot:
        fig.tight_layout()
        plt.show()
    # Note: If ax was provided, the CALLER display method is responsible for layout adjustments and plt.show()
    return None

# Helper function to create a boxplot of the question and answer length comparison
def create_ans_len_boxplot(question_lengths: pd.Series,
                           answer_lengths: pd.Series,
                           question_keyword: str,
                           ans_box_color: str = 'thistle', 
                           q_box_color: str = 'purple', 
                           ax: Union[Axes, None] = None) -> None: 
    # pylint: disable=unsubscriptable-object
    """
    Generates a boxplot comparing question and answer lengths for keyword-filtered data.
    It displays a horizontal matplotlib boxplot visualizing the distribution of these lengths together using distinct 
    colors for question and answer length distributions.

    :param question_lengths: Series of (non-empty) numerical question lengths (typically derived from get_clean_word_counts).
    :type question_lengths: pd.Series[int]
    :param answer_lengths: Series of (non-empty) numerical answer lengths (typically derived from get_clean_word_counts).
    :type answer_lengths: pd.Series[int]
    :param ans_box_color: The color used to fill the boxplot for the 'Answer Lengths'. 
        Defaults to 'thistle'. Any valid matplotlib color string is accepted.
    :type ans_box_color: str, optional
    :param q_box_color: The color used to fill the boxplot for the 'Question Lengths'. 
        Defaults to 'purple'. Any valid matplotlib color string is accepted., defaults to 'purple'.
    :type q_box_color: str, optional
    :param ax: The matplotlib Axes object to plot on. In case of None, a standalone figure is created.
    :type ax: plt.Axes | None
    
    :return: Display the boxplot and return None
    :rtype: None    
    """
    # Prepare Data and Labels Lists for boxplot
    plot_data = [answer_lengths, question_lengths] 
    plot_labels = ['Answer Lengths', 'Question Lengths']
    colors = [ans_box_color, q_box_color]
    if ax is None:
        # If no axes provided, create new figure and axes for standalone plot
        fig, ax = plt.subplots(figsize=(10, 5))
        standalone_plot = True
    else:
        # Use the provided axes
        fig = ax.figure # Get the figure the axes belongs to
        standalone_plot = False

    # common box properties 
    box_plot_dict = ax.boxplot(plot_data,
                                labels=plot_labels,
                                meanline=True,
                                vert=False,
                                showfliers=True,
                                patch_artist=True,
                                boxprops=dict(linewidth=1) 
                                )
    for patch, color in zip(box_plot_dict['boxes'], colors):
        patch.set_facecolor(color)
        
    ax.set_title(f"Distribution of Question vs. Answer Lengths for '{question_keyword}' questions")
    ax.set_xlabel('Word count')
    # only when standalone_plot is True to display the plot
    if standalone_plot:
        fig.tight_layout()
        plt.show()
    # Note: If ax was provided, the CALLER display method is responsible for layout adjustments and plt.show()
    return None
    
# Helper function to print the interpretation of the correlation results

def interpret_correlation(r_value: float, p_value: float, alpha: float =0.05) -> tuple[str, str]:
    """
    Generates a descriptive string interpreting correlation significance and strength.

    Combines statistical significance (based on p-value and alpha) with
    qualitative strength (based on r_value) into a single summary string.

    :param r_value: Pearson correlation coefficient.
    :param p_value: P-value from the correlation test.
    :param alpha: Significance level threshold. Default 0.05.
    :return: A string summarizing the correlation interpretation.
    :rtype: str
    """
    if pd.isna(p_value) or pd.isna(r_value):
        return "Insufficient data or calculation error for correlation", 'N/A'

    # Determine Significance
    is_significant = p_value < alpha

    # Determine Strength (using existing helper)
    strength_desc = get_correlation_strength(r_value)

    # Combine into final string
    if is_significant:
        # Only include strength detail if significant
        interpretation_string= f"Statistically significant (correlation is {strength_desc})"
    else:
        interpretation_string = "Not statistically significant"
        interpretation_string += f" (r={r_value:.3f})"

    return interpretation_string, strength_desc


#=====================================#
##  B. ANALYSIS ORCHESTRATION FUNCTION #
#=====================================#

# A wrapper function that validates and manages helper functions to gather kewyord metrics for the keyword display method.
def calculate_keyword_metrics(question_keyword: str, dataframe: pd.DataFrame) -> Union[dict[str, Any], None]:
    """
    Calculates and returns key metrics for a given question keyword in the provided DataFrame.

    This function performs input validation, filters the DataFrame by the keyword,
    calculates descriptive statistics for question and answer lengths, and calculates
    the correlation between the q&a lengths.  It returns a dictionary containing these metrics.
    If no questions are found for the keyword or the input is invalid, it may return None.

    :param question_keyword: The keyword to filter questions by.
    :type question_keyword: str
    :param dataframe: The DataFrame containing question and answer data.
    :type dataframe: pd.DataFrame
    :raises ValueError: If input is invalid (e.g., not a DataFrame, empty DataFrame,
                        invalid keyword).
    :return: A dictionary containing metrics like counts, percentages, descriptive
             statistics for question and answer lengths, correlation coefficient,
             p-value, correlation strength, and interpretation.  Returns None if
             the input DataFrame is empty or no questions are found for the keyword.
    :return: A dictionary ('results package') containing:
         - 'keyword_for_display' (str): The input keyword, for display purposes.
         - 'metrics_for_summary' (dict): Metrics for table rows (does NOT include keyword).
         - 'filtered_data_df' (pd.DataFrame): The filtered DataFrame.
         - 'q_lengths_series' (pd.Series): Question lengths.
         - 'a_lengths_series' (pd.Series): Answer lengths.
         Returns None if initial filtering finds no data or major validation fails.
    """
    # Step 0: Input validation
    if not isinstance(dataframe, pd.DataFrame):
        raise ValueError("The input must be a pandas DataFrame.")
    if not isinstance(question_keyword, str):   
        raise ValueError("The keyword must be a string.")
    if question_keyword == "":  
        raise ValueError("The keyword cannot be an empty string.")
    if dataframe.empty:
        raise ValueError("The input DataFrame is empty.")  
    
    # Step 1: Filter the dataframe by the keyword
    filter_kw_questions = filter_df_by_keyword(dataframe, question_keyword)
    # check the results of the filtering
    kw_question_count = filter_kw_questions.shape[0]
    kw_percentage = (kw_question_count / dataframe.shape[0]) * 100
    
    if filter_kw_questions.empty:
        print(f"INFO: No questions found for keyword '{question_keyword}'.")
        return None
        # Will return filtered dataframe by question keyword or empty dataframe
    else:
        # Step 2: Get the lengths of questions and answers
        question_lengths = get_clean_word_counts(filter_kw_questions, 'question') #type: ignore
        answer_lengths = get_clean_word_counts(filter_kw_questions, 'answer')     #type: ignore
        # Each will return a Series of word counts for the respective column
        
        # Sanity check to make sure the question and answer lengths match
        if question_lengths.empty or answer_lengths.empty:
            print(f"WARNING: No data available for keyword '{question_keyword}'.")
            return None
        if len(question_lengths) != len(answer_lengths):
            print(f"ERROR: Length mismatch after word count for '{question_keyword}'.")
            return None
        # Step 3: get the descriptive statistics for question and answer lengths
        descriptive_stats = get_len_descriptive_stats(question_keyword, question_lengths, answer_lengths)
        # will return a dict with the descriptive stats for the questions and answer lengths for the keyword.
        
        # Step 4: Calculate the correlation coefficient and p-value
        if kw_question_count < 2: # Not enough data for correlation
            print(f"WARNING: Insufficient data (N={kw_question_count}) for correlation for keyword '{question_keyword}'.")
            r_coeff, p_val = np.nan, np.nan
            r_strength = 'N/A'
            interpretation = 'Insufficient data for correlation'
        else:
            r_coeff, p_val = calculate_correlation(question_lengths, answer_lengths)
            interpretation, r_strength = interpret_correlation(r_coeff, p_val)
        
        # Step 5: Create a summary dictionary with all the results
        results = {
            'question_count': kw_question_count,
            'question_percentage': kw_percentage,
            'question_mean': descriptive_stats['question_mean'],
            'question_std': descriptive_stats['question_std'],
            'question_min': descriptive_stats['question_min'],
            'question_max': descriptive_stats['question_max'],
            'question_median': descriptive_stats['question_median'],
            'question_25th_percentile': descriptive_stats['question_25th_percentile'],
            'question_75th_percentile': descriptive_stats['question_75th_percentile'],
            'question_iqr': descriptive_stats['question_iqr'],
            'question_range': descriptive_stats['question_range'],
            'question_skew': descriptive_stats['question_skew'],
            'answer_count': descriptive_stats['answer_count'],
            'answer_mean': descriptive_stats['answer_mean'],
            'answer_std': descriptive_stats['answer_std'],
            'answer_min': descriptive_stats['answer_min'],
            'answer_max': descriptive_stats['answer_max'],
            'answer_median': descriptive_stats['answer_median'],
            'answer_25th_percentile': descriptive_stats['answer_25th_percentile'],
            'answer_75th_percentile': descriptive_stats['answer_75th_percentile'],
            'answer_iqr': descriptive_stats['answer_iqr'],
            'answer_range': descriptive_stats['answer_range'],
            'answer_skew': descriptive_stats['answer_skew'],
            'correlation_r': r_coeff,
            'correlation_p': p_val,
            'correlation_strength': r_strength,
            'interpretation': interpretation
        }
        # Step 6: Package everything needed downstream (for display or summary)
        results_package = {
            'keyword_for_display': question_keyword, # The keyword for display
            'metrics': results,                      # The metrics dictionary
            'filtered_df': filter_kw_questions,      # The filtered data
            'q_lengths': question_lengths,           # The length Series
            'a_lengths': answer_lengths              # The length Series
            }
        return results_package

# Aggregate function to gather metrics for keywords and
# Create a comprehensive summary dataframe for generating various summary tables
def create_comprehensive_summary_df(question_keyword_list: list, factual_keywords_list: list,
                                       dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Generates a summary DataFrame of Q&A length that contains a comprehensive metrics generated 
    by the `calculate_keyword_metrics` function for each keyword in the provided list. The helper
    functions 'display_correlation_summary()` and `display_status_map` can be used to create set views.
    Custom views can also be created by filtering and printing 'summary_df' in the notebook.
     
    NOTE: This method calls the manager function `calculate_keyword_metrics` for each keyword. 
    The keyword from the input list is then used as the primary identifier for each row in the 
    output summary DataFrame, combined with the 'metrics_for_summary'data returned by the manager. 
    
    :param question_keyword_list: List of keywords to include in the summary dataframe
    :type question_keyword_list: list
    :param factual_keywords_list: List of keywords from the `question_keyword_list` that are 
            consdidered 'factual-recall' type.
    :type factual_keywords_list: list
    :param dataframe: The DataFrame containing question and answer data.
    :type dataframe: pd.DataFrame
    
    :return: A DataFrame with a comprehensive summarizing the metrics for each keyword.
    :rtype: pd.DataFrame
    """
    # Initialize the main dictionary. 
    # This dict will contain a nested dictionary of metrics for each keyword.
    all_keyword_metrics = {} 
    
    # Loop through the keywords to populate dictionary
    for keyword in question_keyword_list:
        # Check if the keyword is in the list of factual keywords 
        is_factual = keyword in factual_keywords_list
        # Assign the question type label based on the keyword
        q_type_label = 'Factual-Recall' if is_factual else 'Non-Factual'
        
        # calculate the metrics for keyword
        metrics_package = calculate_keyword_metrics(keyword, dataframe,)
        
        # make sure it is not None then add to the 'metrics' to dictionary:
        if metrics_package:
            all_keyword_metrics[keyword] = metrics_package['metrics'].copy()
            all_keyword_metrics[keyword]['question_type'] = q_type_label 
           
    # Create the comprehensive summary DataFrame
    summary_df = pd.DataFrame.from_dict(all_keyword_metrics, orient='index')
    summary_df.index.name = 'Keyword'
    summary_df = summary_df.reset_index()
    summary_df = summary_df.sort_values(by='question_count', ascending=False)
    
    return summary_df

#===============================================#
## C. DISPLAY ORCHESTRATION and VIEW FUNCTIONS  #
#===============================================#

def plot_qa_len_distributions(question_lengths, answer_lengths):
    """_summary_

    :param question_lengths: _description_
    :param answer_lengths: _description_
    """
    
    # Create subplots
    # A 1x2 grid of plots
    fig, axs = plt.subplots(2,1,figsize=(12, 8))

    # PLOT 1: Plot a histogram of the distribution of question lengths
    bin_edges = np.arange(0, 32 + 1, 1) # to make sure the bin edges are int for easier interpretation
    axs[0].hist(question_lengths, bins=bin_edges, color='purple', alpha=0.7,align='mid')
    axs[0].hist(answer_lengths, bins=bin_edges, color='thistle', alpha=0.7,align='mid')
    axs[0].set_title("Distribution of Question and Answer Lengths")
    axs[0].set_xlabel("Sentence length (based on word count)")
    axs[0].set_ylabel("Frequency")
    axs[0].legend(["Questions", "Answers"])
    axs[0].grid(True, linestyle='--', alpha=0.6)

    # PLOT 2: Boxplot for question and answer lengths
    # update figure_count for visual:
    box = axs[1].boxplot([ answer_lengths, question_lengths], vert=False, patch_artist=True,
                tick_labels=["Answers", "Questions"],
                boxprops=dict(color="black"),  # Box border color
                medianprops=dict(color="black", linewidth=2),  # Median line in black
                meanline=True, showmeans=True, meanprops=dict(color="black", linewidth=2)
                )
    # Fill colors for boxes
    colors = ["thistle", "purple"]
    for patch, color in zip(box["boxes"], colors):
        patch.set(facecolor=color, alpha=0.7)  # Set fill color
    axs[1].set_title("Boxplot of Question and Answer Lengths")
    axs[1].set_xlabel("Sentence Length (based on word count)")
    # Create legend handles
    legend_elements = [
        Line2D([0], [0], color="black", linewidth=2, label="Median Line"),
        Line2D([0], [0], color="black", linewidth=2, linestyle="--", label="Mean Line", alpha=0.5)
    ]
    # Add legend to boxplot
    axs[1].legend(handles=legend_elements, loc="upper right")
    axs[1].grid(True, linestyle='--', alpha=0.6)

    # Ensure both plots have the same x-axis range
    axs[1].set_xlim(axs[0].get_xlim())
    # Set x-axis ticks to go up in unit steps
    combined_lengths = pd.concat([question_lengths, answer_lengths])
    overall_min = int(np.floor(combined_lengths.min())) # Use floor for min
    overall_max = int(np.ceil(combined_lengths.max()))  # Use ceil for max
   
    xlim_min = max(0, overall_min - 1) # Pad by 0.5 to see tick 0 clearly
    xlim_max = overall_max + 0.5

    for ax_obj in axs:
        ax_obj.set_xlim(xlim_min, xlim_max)
        # Force ticks at every integer multiple of 1
        ax_obj.xaxis.set_major_locator(MultipleLocator(1))

    plt.tight_layout() # Adjust rect for suptitle if needed
    plt.show()

    return None

def display_keyword_analysis(results_package: Optional[dict[str, Any]],n_samples: int = 5):
    """
    Displays a standardized set of analysis results for a given keyword,
    using the provided results package. The results package is exptected 
    to be created with the calculate_keyword_metrics function in a separate
    function call.

    Includes: Count/Percentage, Descriptive Stats Table, Correlation Info & Plot,
              Box Plot of Lengths, and Sample DataFrames.

    :param results_package: Dictionary (or None) returned by calculate_keyword_metrics;
                            expected keys are 'keyword_for_display', 'metrics', 
                            'filtered_data', 'q_lengths', 'a_lengths'.
    :param n_samples: Number of sample rows to display. Default 5.
    
    :return: None
    :rtype: None
    """
    # Check if results_package exists
    if results_package is None:
        print("No results package provided. Cannot display analysis.")
        return
    
    # Step 2: Extract the arguments from the results package
    question_keyword = results_package.get('keyword_for_display', 'Unknown Keyword')    
    metrics_dict = results_package.get('metrics',{})
    question_lengths = results_package.get('q_lengths', None)
    answer_lengths = results_package.get('a_lengths', None)
    filtered_df = results_package.get('filtered_df', None)
    count = metrics_dict.get('question_count', 0)

    # Handle case where filtered_df might be None even if metrics_dict exists (e.g. length error)
    if filtered_df is None and count > 0:
        print(f"WARNING: Metrics found for '{question_keyword}', but filtered data is missing. Cannot display samples or plots reliably.")

    percentage = metrics_dict.get('question_percentage', 0.0)
    # Display header at the top of the output
    display(Markdown(f"## Analysis for Keyword: '{question_keyword.upper()}'"))

    # 1. Display the count and percentage of questions
    print(f"Number of Questions: {count} ({percentage:.1f}% of total)")

    # 2. Display the descripttive statistics table (for question and answer lengths)
    stats_df = format_descriptive_stats_table(metrics_dict)
    display(stats_df)
    
    # Display correlation values
    print("\nCorrelation between Question and Answer Length:")
    if count < 2:
        print("- Interpretation: Insufficient data for correlation (N < 2)")
    else:
        interpretation = metrics_dict.get('interpretation', 'N/A - Check calculation')
        r_val = metrics_dict.get('correlation_r', np.nan)  # value check in case NaN
        p_val = metrics_dict.get('correlation_p', np.nan)  # value check in case NaN
        print(
            f"* Interpretation: {interpretation}\n"
            f"* Pearson's r = {r_val:.3f}, P-value = {p_val:.3f}"
              )

    # 3. Display scatter plot and length comparison boxplot as subplots in the same figure
    if count > 0 and question_lengths is not None and answer_lengths is not None:
        # Create figure with two subplots (1 column, 2 rows)
        fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(10, 10)) 
        # Create scatter plot on the first subplot
        create_correlation_scatterplot(question_lengths, answer_lengths, question_keyword, ax=axes[0])
        # create boxplot on the second subplot
        create_ans_len_boxplot(question_lengths, answer_lengths, question_keyword, ax=axes[1])
        fig.tight_layout(pad=2.0) # Adjust layout for the whole figure
        plt.show() # Show the single figure with both subplots

    # 4. Display a random sample of the filtered DataFrame
    print(f"\nRandom Sample ({n_samples}) of '{question_keyword}' Questions:")
    actual_samples = min(n_samples, count)
    if actual_samples > 0 and filtered_df is not None:
        display(filtered_df.sample(actual_samples))
    elif filtered_df is None:
        print("Cannot display samples as filtered data was not provided/available.")
    else:
        print("No samples to display.")
    print("-" * 70) # End separator
                   
def display_correlation_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Formats a subset of the master summary DataFrame for displaying correlation insights.

    Selects, formats, and displays a summary view for correlation insights
    from the master summary DataFrame.

    :param summary_df: The comprehensive summary DataFrame (output of
                       create_comprehensive_summary_table) containing all metrics.
                       Expected columns include: 'Keyword', 'question_type',
                       'question_count', 'question_percentage', 'question_mean',
                       'answer_mean', 'correlation_r', 'correlation_p', 'interpretation'.
    :type summary_df: pd.DataFrame
    :return: None
    :rtype: None
    """
    # create a columns to display in the table from the comprehensive summary df
    columns_to_display =['Keyword', 
                         'question_type', 
                         'question_count', 
                         'question_percentage', 
                         'question_mean', 
                         'answer_mean',
                         'correlation_r',
                         'correlation_p', 
                         'interpretation']
    
    # copy and filter the summary df
    correlation_summary_df = summary_df[columns_to_display].copy()
    # rename the columns for display
    correlation_summary_df = correlation_summary_df.rename(columns={
        'Keyword': 'Question Keyword',
        'question_count': 'Keyword Count',
        'question_percentage': '(%) of total',
        'question_mean': 'Mean Question Length',
        'answer_mean': 'Mean Anwer Length',
        'correlation_r': "Pearson's r",
        'correlation_p': "P-value",
        'interpretation': "Interpretation"
    })
    # sort the columns by keyword count and round the values
    correlation_summary_df = correlation_summary_df.sort_values(by='Keyword Count', ascending=False).round({
    'perc. of total': 0,
    'Mean Ques Length': 0,
    'Mean Ans Length': 0,
    "Pearson's r": 3,
    "P-value": 3
})
    # display the correlation summary table
    print("\nCorrelation Summary Table by Question Keywords:")
    display(correlation_summary_df)

def display_status_map(summary_df: pd.DataFrame) -> None:
    """ 
    Formats a subset of the master summary DataFrame for displaying the status map
    of the dataset. This is a summary view of questions types and their counts and 
    percentages to give an idea of the diversity of question types within the dataset.

    Selects, formats, and displays a summary view for the status map view from the 
    master summary DataFrame.

    :param summary_df: The comprehensive summary DataFrame (output of
                       create_comprehensive_summary_table) containing all metrics.
                       Expected columns include: 'Keyword', 'question_type',
                       'question_count', 'question_percentage', 'question_mean',
                       'answer_mean', 'correlation_r', 'correlation_p', 'interpretation'.
    :type summary_df: pd.DataFrame
    :return: None
    :rtype: None
    """
    # List of columns to display in the status map
    columns_to_display =  ['Keyword', 'question_type', 'question_count', 'question_percentage']
    
    # copy and filter the summary df
    status_map_df = summary_df[columns_to_display].copy()
    
    # rename the columns for display
    status_map_df = status_map_df.rename(columns={
        'Keyword': 'Question Keyword',
        'question_count': 'Keyword Count',
        'question_percentage': '(%) of total'
    })  
    
    # sort the columns by keyword count
    status_map_df = status_map_df.sort_values(by='Keyword Count', ascending=False).round({
    'perc. of total': 0,
    'Mean Ques Length': 0,
    'Mean Ans Length': 0,
})
    # display the status map in the notebook
    print("\nStatus Map of the Trivia dataset based on Question Types:")
    display(status_map_df)
#=====================================#
## D. N-GRAM UTILITY FUNCTIONS        #
#=====================================#

# Custom function for a keyword N-gram analysis later? e.g. "is it" or "how many"
def print_common_ngrams(questions_series: pd.Series, ngram_range: tuple = (2, 3), top_n: int = 10) -> None:
    '''
    Analyzes a pandas Series of text (question strings) to find common n-grams
    and prints the top N most frequent ones.

    parameters:
    questions_series (pd.Series): A pandas Series containing the text strings to analyze.
                                   Expected to contain question text from a filtered DataFrame.
    ngram_range (tuple): The lower and upper boundary of the range of n-values for the n-grams.
                         e.g., (1, 1) for unigrams, (2, 3) for bigrams and trigrams.
                         Defaults to (2, 3).
    top_n (int): The number of top most frequent n-grams to display. Defaults to 10.
    '''
    print("\nAnalyzing common phrases (n-grams) in this set of questions:")

    # Ensure input is a Series and drop any potential missing values
    if not isinstance(questions_series, pd.Series):
        print("Error: Input for n-gram analysis must be a pandas Series.")
        return

    questions_text = questions_series.dropna()

    if questions_text.empty:
        print("No text data available for n-gram analysis after dropping missing values.")
        return

    # Initialize CountVectorizer
    # stop_words='english' removes common words like 'the', 'is', 'in'
    vectorizer = CountVectorizer(ngram_range=ngram_range, stop_words='english')

    try:
        # Fit the vectorizer to the text and transform it into a matrix of token counts
        ngram_matrix = vectorizer.fit_transform(questions_text)

        # Get the names of the features (the n-grams)
        feature_names = vectorizer.get_feature_names_out()

        # Sum the counts of each n-gram across all questions
        ngram_counts = ngram_matrix.sum(axis=0)

        # Create a list of n-gram and count pairs
        ngram_freq = [(feature_names[i], ngram_counts[0, i]) for i in range(len(feature_names))]

        # Sort the n-grams by frequency in descending order
        ngram_freq = sorted(ngram_freq, key=lambda x: x[1], reverse=True)

        # Print the top N most common n-grams
        print(f"Top {min(top_n, len(ngram_freq))} common n-grams:") # Print up to the actual number of unique ngrams found
        if ngram_freq: # Only iterate if there are ngrams found
            for ngram, count in ngram_freq[:top_n]:
                print(f"- '{ngram}': {count}")
        else:
            print("No n-grams found based on the specified range and stop words.")

    except Exception as e:
        print(f"An error occurred during n-gram analysis: {e}")


def print_keyword_ngrams(
    questions_series: pd.Series,
    keyword: str,
    ngram_range: tuple = (2, 3),
    top_n: int = 10,
    # Use Union explicitly to define the allowed types plus None
    stop_words: Union[str, List[str], None] = None
) -> None:
    '''
    Analyzes a pandas Series of text to find common n-grams starting with a specific keyword
    and prints the top N most frequent ones. Allows optional removal of stop words
    during n-gram generation.

    Parameters:
        questions_series (pd.Series): A pandas Series containing the text strings to analyze.
                                       Expected to contain question text.
        keyword (str): The keyword or phrase the n-grams must start with (case-insensitive).
                       e.g., "what", "how many", "is it".
        ngram_range (tuple): The lower and upper boundary of the range of n-values for the n-grams.
                             e.g., (2, 2) for bigrams, (2, 3) for bigrams and trigrams.
                             Defaults to (2, 3).
        top_n (int): The number of top most frequent keyword-specific n-grams to display.
                     Defaults to 10.
        stop_words (Union[str, List[str], None]): Controls stop word removal *before* n-gram creation.
                     - None (default): No words are removed. Use this if your `keyword`
                       contains common words (e.g., "is it", "what is").
                     - 'english': Uses scikit-learn's built-in English stop word list.
                     - List[str]: Provide your own custom list of words to remove.
                     *** Important Limitation: ***
                     If your `keyword` itself contains words that are also in the `stop_words`
                     list being used, the function will likely NOT find matches.
    '''
    print(f"\nAnalyzing common phrases (n-grams) starting with '{keyword}' in this set of questions:")
    print(f"Using stop_words: {stop_words}") # Explicitly show the setting being used

    # --- Input Validation ---
    if not isinstance(questions_series, pd.Series):
        print("Error: Input 'questions_series' must be a pandas Series.")
        return
    if not keyword or not isinstance(keyword, str):
        print("Error: A valid 'keyword' string must be provided.")
        return

    # --- Data Preparation ---
    questions_text = questions_series.dropna()
    if questions_text.empty:
        print("No text data available for n-gram analysis after dropping missing values.")
        return

    # Prepare keyword: lowercase and strip whitespace for reliable matching
    keyword_lower = keyword.lower().strip()
    if not keyword_lower:
        print("Error: Keyword cannot be empty or only whitespace.")
        return

    # --- N-gram Calculation ---
    # Pass the user-provided stop_words setting to the vectorizer
    # This call should now better align with Pylance's understanding of the Union type
    vectorizer = CountVectorizer(ngram_range=ngram_range, stop_words=stop_words, lowercase=True)

    try:
        # Fit the vectorizer and transform the text
        ngram_matrix = vectorizer.fit_transform(questions_text)

        # Get the feature names (the n-grams after potential stop word removal)
        feature_names = vectorizer.get_feature_names_out()

        # Check if any features were generated after stop word removal
        if not feature_names.size:
             print(f"No features (n-grams) were generated. This might be due to all words being filtered by stop_words='{stop_words}', empty input, or very short texts.")
             return

        # Sum the counts of each n-gram
        ngram_counts = ngram_matrix.sum(axis=0)

        # Create a list of all generated n-gram and count pairs
        all_ngram_freq = [(feature_names[i], ngram_counts[0, i]) for i in range(len(feature_names))]

        # --- Filtering by Keyword ---
        keyword_ngram_freq = []
        for ngram, count in all_ngram_freq:
            if ngram.startswith(keyword_lower + " ") or ngram == keyword_lower:
                keyword_ngram_freq.append((ngram, count))

        # Sort the filtered n-grams by frequency in descending order
        keyword_ngram_freq = sorted(keyword_ngram_freq, key=lambda x: x[1], reverse=True)

        # --- Output Results ---
        print(f"Top {min(top_n, len(keyword_ngram_freq))} common n-grams starting with '{keyword}':")
        if keyword_ngram_freq:
            for ngram, count in keyword_ngram_freq[:top_n]:
                print(f"- '{ngram}': {count}")
        else:
            if not all_ngram_freq:
                pass # Already handled by feature_names.size check
            else:
                print(f"No n-grams found starting with '{keyword}'.")
                if stop_words:
                   print(f"   Note: This might happen if the keyword '{keyword}' itself was affected by the stop_words setting ('{stop_words}'), or if no matching n-grams exist in the data.")
                else:
                    print("   Note: No matching n-grams exist in the data.")


    except ValueError as ve:
        print(f"An error occurred during n-gram analysis: {ve}")
        print(f"This might happen if the vocabulary becomes empty after applying stop_words='{stop_words}'.")
    except Exception as e:
        print(f"An unexpected error occurred during n-gram analysis: {e}")
        
# Estimate difficulty of a question with TF-IDF
def rank_ngrams_by_tfidf(dataframe: pd.DataFrame,
                         column_name: str, 
                         ngram_range: tuple = (1, 2),
                         max_df: Union[int, float] = 1.0,
                         min_df: Union[int,float] = 1,
                         stop_words: Union[list[str],None] = None) -> pd.DataFrame:
    """
    This method uses tf-idf vectorization to find n-grams in a Series (with the already tokenized
    `answer keywords` or `question keywords` columns) as a proxy for difficulty. 
    It uses the `idf_score` as a measure of rarity, obscurity, or uniqueness.
    It uses the `summed_TFIDF_score` of the n-gram as a measure of its overall importance within the
    dataset.

    :param dataframe: Input dataframe that is to be analyzed.
    :type dataframe: pd.DataFrame
    :param column_name: The column to create n-grams from (expects 'answer keywords' or 'question keywords')
    :type column_name: str
    :param ngram_range: Range (min, max) of n-grams to consider.
    :type ngram_range: tuple[int, int]
    :param max_df: Maximum document frequency threshold (optional, default is 1.0, same as the tfidfvectorizer)
    :type max_df: Union[int, float]
    :param min_df: Minimum document frequency threshold (optional, default is 1, same as the tfidfvectorizer)
    :type min_df: Union[int, float]
    
    :return tfidf_scores_df: A dataframe of the `n-grams` and their `idf_score` and `sum_tfidf_score`. 
    :rtype: pd.DataFrame 
    """
    df_tfidf = dataframe.copy()
    
    # 1. Prepare the `answer keywords` column for tf-idf. 
    #    Convert the list of tokens into a string 
    new_column_name = column_name + '_txt'
    df_tfidf[new_column_name] = df_tfidf[column_name].apply(lambda token_list: ' '.join(token_list))
    
    # 2. Initialize the tf-idf vectorizer:
    vectorizer = TfidfVectorizer(
        stop_words= stop_words,
        ngram_range= ngram_range,
        max_df = max_df,
        min_df = min_df,
    )
   # 3. Fit the vectorizer on the answer keywords
    vectorizer.fit(df_tfidf[new_column_name])
    # 4. Get the N-grams
    n_grams = vectorizer.get_feature_names_out()
    # 5. Get the obscurity / rareness score, ie. the idf score iteslf
    rarity_idf_score = vectorizer.idf_
    # 6. Get the overall importance score
    tfidf_matrix = vectorizer.transform(df_tfidf[new_column_name])
    summed_tfidf = np.asarray(tfidf_matrix.sum(axis=0)).ravel()
    # 7. Create a score dataframe to return the results with
    tfidf_scores_df = pd.DataFrame({
        'n-gram' : n_grams,
        'idf_score' : rarity_idf_score,
        'summed_tfidf_score' : summed_tfidf
    }) 
    return tfidf_scores_df.round(2)