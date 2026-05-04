import sys
sys.path.insert(0, 'sagemaker')

# Simulate SageMaker paths using local data
from pathlib import Path
import engineer_v2 as eng

# Override paths to use local data
eng.INPUT_RAW = Path("data/raw")
eng.OUTPUT_PATH = Path("data/sagemaker_test_output")

# Create local raw directory with the right files
import os, shutil
os.makedirs("data/raw", exist_ok=True)
shutil.copy("data/raw_game_results.csv", "data/raw/game_results.csv")
shutil.copy("data/game_schedule.csv", "data/raw/game_schedule.csv")
shutil.copy("data/pitching_stats.csv", "data/raw/pitching_stats.csv")

eng.main()