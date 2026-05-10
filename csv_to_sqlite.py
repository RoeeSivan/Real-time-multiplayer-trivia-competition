import pandas as pd
import sqlite3

# 1. Load the CSV you just cleaned
df = pd.read_csv('final_267.csv')

# 2. Create a connection to a new SQLite database
# (This will create 'trivia.db' in your folder if it doesn't exist)
conn = sqlite3.connect('trivia.db')

# 3. Write the data to a SQLite table named 'questions'
# if_exists='replace' ensures you can run this script multiple times safely
df.to_sql('questions', conn, if_exists='replace', index=False)

# 4. Close the connection
conn.close()

print("Successfully converted CSV to SQLite database!")