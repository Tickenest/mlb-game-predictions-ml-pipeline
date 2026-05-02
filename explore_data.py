import pandas as pd

df = pd.read_csv("data/raw_game_results.csv")

print("=== Basic Info ===")
print(f"Shape: {df.shape}")
print(f"\nW/L value counts:")
print(df['W/L'].value_counts())

print(f"\nHome_Away value counts:")
print(df['Home_Away'].value_counts())

print(f"\nSeason value counts:")
print(df['season'].value_counts().sort_index())

print(f"\nNull counts:")
print(df.isnull().sum()[df.isnull().sum() > 0])

print(f"\nSample of rows with unusual W/L values:")
print(df[~df['W/L'].isin(['W', 'L', 'W-wo', 'L-wo'])].head(20))