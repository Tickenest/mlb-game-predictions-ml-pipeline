import pandas as pd
pitching = pd.read_csv("data/pitching_stats.csv")
print(sorted(pitching['Tm'].unique().tolist()))