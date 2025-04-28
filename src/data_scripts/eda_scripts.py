## Custom functions for question keyword analysis

from typing import List, Union # For Python < 3.10
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import CountVectorizer
from IPython.display import display

#---------------------
## Helper functions:

# 1. Helper function to filter dataframe based on keyword
def filter_df_by_keyword(dataframe: pd.DataFrame, keyword: 'str') -> Union[pd.DataFrame, None]:
    '''
    This function filters for questions based on a search of the keyword provided in the `question keywords` column.

    parameters:
    dataframe (pd.DataFrame): the data frame on which to perform the search on. The dataframe MUST have a column with a
    list of tokens generated from the question and the column is called `question keywords`!
    
    keyword (str): the search word to look for in the token lists for each question in the `question keywords` column

    returns:
    pd.DataFrame | None: The filtered dataframe if matches are found (which might be empty but not None), or None
                         if no questions found or on filtering error.
    '''
    # Filter main dataframe
    filter_kw_questions = dataframe.loc[dataframe['question keywords'].apply(lambda x: keyword in x)]

    # Calculate the number of questions filtered out
    filtered_question_count = filter_kw_questions.shape[0] 

    # Check: did the filter find matches? if not, return message and exit early.
    if filtered_question_count == 0:
        print(f"No questions found containing the keyword '{keyword}'.")
        return # Exit the function early
    else:
        return filter_kw_questions

# 2. Helper function that returns a Series with the length of each answer  
def get_str_lengths(dataframe: pd.DataFrame, column_name: str) -> pd.Series:
    """Helper function that returns a Sries with the length of each answer that can be used for further analysis

    :param dataframe: source dataframe that has the trivia `answer` column to be analysed.
    :return: Series with answer lengths
    """
    return dataframe[column_name].str.len()

#---------------------
## Functions for keyword analysis

# 1. Custom function to access question by a keyword, e.g. "which" or "why" 
def get_question_type_info(dataframe: pd.DataFrame ,keyword: str, n_samples: int) -> None:
    '''
    This function filters for questions based on a search of the keyword provided in the `question keywords` column.
    It then prints:
    - count and percentage that these keyword-type questions appear in the datset
    - range of their respective answer lengths
    - a n_sample view of the dataframe

    parameters:
    keyword (str): the search word to look for in the token lists for each question in the `question keywords` column
    n_samples (int): the number of samples to display from the filtered dataframe.
    '''
    # Use the helper function to filter the df by keyword:
    filter_kw_questions = filter_df_by_keyword(dataframe, keyword)

    # Calculate the number of questions filtered out
    if filter_kw_questions is not None:
        filtered_question_count = filter_kw_questions.shape[0] 

        # Get answer length using helper function
        fq_ans_len = get_str_lengths(filter_kw_questions, 'answer')
        min_ans_len = fq_ans_len.min()
        max_ans_len = fq_ans_len.max()
        total_question_count = dataframe.shape[0]

        # Percentage
        filtered_percentage = (filtered_question_count/total_question_count)*100

        # Sanity check on the provided "n_samples"
        actual_samples = min(n_samples, filtered_question_count)

        # display results
        print(f"There are {filtered_question_count} '{keyword}'-type questions in the data set ({filtered_percentage: .0f}% of total).")
        print(f"These questions have answers that range in lengths between {min_ans_len} and {max_ans_len}.\n")
        print(f"Basic descriptive statistics of the answers with '{keyword}' type questions: \n", fq_ans_len.describe())
        print(f"\nA random sample of the `{keyword}`- type questions: ")

        # display df
        if actual_samples > 0: # Only try to sample if there are samples to take
            display(filter_kw_questions.sample(actual_samples))
        else:
        # catchall incase of typo / input error
            print("No samples to display.")

        
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
         
def create_ans_len_boxplot(dataframe: pd.DataFrame, keyword: str, ans_box_color: str = 'thistle', q_box_color: str = 'plum' ):
    ''''Generates a boxplot comparing question and answer lengths for keyword-filtered data.

    This function filters an input DataFrame based on a keyword found in the 
    'question keywords' column. It then calculates the string lengths for both the 
    'question' and 'answer' columns corresponding to the filtered rows using a 
    helper function. Finally, it displays a horizontal matplotlib boxplot 
    visualizing the distribution of these lengths side-by-side, using distinct 
    colors for question and answer length distributions.

    Note: This function relies on external helper functions `filter_df_by_keyword` 
    and `get_str_lengths` to perform filtering and length calculations, respectively.

    Parameters
    ----------
    dataframe : pd.DataFrame
        The input DataFrame containing the data. It is expected to have at least 
        the following columns: 'question keywords', 'question', and 'answer'.
    keyword : str
        The keyword string used to filter the `dataframe` based on the 
        contents of the 'question keywords' column (via `filter_df_by_keyword`).
    ans_box_color : str, optional
        The color used to fill the boxplot for the 'Answer Lengths'. 
        Defaults to 'thistle'. Any valid matplotlib color string is accepted 
        (e.g., 'red', '#FF00FF').
    q_box_color : str, optional
        The color used to fill the boxplot for the 'Question Lengths'. 
        Defaults to 'plum'. Any valid matplotlib color string is accepted.

    Returns
    -------
    None
        This function displays a plot directly using `plt.show()` and does not 
        return any value.

    Raises
    ------
    Exception
        May raise exceptions originating from the helper functions 
        (`filter_df_by_keyword`, `get_str_lengths`) or matplotlib if data 
        processing or plotting fails (e.g., due to missing columns in the 
        filtered data, non-string data preventing length calculation by 
        `get_str_lengths`, etc.). The function includes a basic check 
        if the result from `filter_df_by_keyword` is None. 
    '''

    # Use the helper function to filter the df by keyword:
    filter_kw_questions = filter_df_by_keyword(dataframe, keyword)
    if filter_kw_questions is not None:
        
        # Use the helper function to get question and answer lengths
        q_len = get_str_lengths(filter_kw_questions, 'question')
        ans_len = get_str_lengths(filter_kw_questions, 'answer')
        
       # Prepare Data and Labels Lists for boxplot
        plot_data = [ans_len, q_len] 
        plot_labels = ['Answer Lengths', 'Question Lengths']
        colors = [ans_box_color, q_box_color]
        
        # Use the Series directly for plotting
        plt.figure(figsize=(10,5))
        # common box properties 
        box_plot_dict = plt.boxplot(plot_data,
                                    labels=plot_labels,
                                    meanline=True,
                                    vert=False,
                                    showfliers=True,
                                    patch_artist=True, # Crucial for filling boxes
                                    boxprops=dict(linewidth=1) # Common props
                                    )
        for patch, color in zip(box_plot_dict['boxes'], colors):
            patch.set_facecolor(color)
            
        plt.title(f"Distribution of Question vs. Answer Lengths for '{keyword}' questions")
        plt.xlabel('String length')
        plt.tight_layout() 
        plt.show()


# generated with Google Gemini 2.5:
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
