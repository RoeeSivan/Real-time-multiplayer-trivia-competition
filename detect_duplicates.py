import pandas as pd
import numpy as np

def clean_and_shuffle_trivia(input_csv, output_csv):
    # Load the raw trivia CSV
    df = pd.read_csv(input_csv)

    # 1. Drop duplicate questions (keeps the first occurrence)
    initial_count = len(df)
    df = df.drop_duplicates(subset=['Question'], keep='first')
    duplicates_removed = initial_count - len(df)
    print(f"Removed {duplicates_removed} duplicate questions.")

    # 2. Randomize the 4 answer columns for every row
    def shuffle_answers(row):
        answers = [row['Answer 1'], row['Answer 2'], row['Answer 3'], row['Answer 4']]
        np.random.shuffle(answers) # Randomize the order
        row['Answer 1'], row['Answer 2'], row['Answer 3'], row['Answer 4'] = answers
        return row

    df = df.apply(shuffle_answers, axis=1)

    # Save the pristine, randomized CSV
    df.to_csv(output_csv, index=False)
    print(f"Saved {len(df)} unique, randomized questions to {output_csv}.")

# Run the script
clean_and_shuffle_trivia('final_trivia_250.csv', 'final_250.csv')