# Testing Trivia class - core logic MVP - manual testing.

# Import module to test functions:
from dotenv import load_dotenv
load_dotenv() 

from HPtrivia_game.trivia import Trivia 
import utils.utils_paths as up

# MANUAL TESTING

# 1. trivia._load_dataset()
# parameters:
project_root = up.find_project_root()
print('Project root: ', project_root)

name = "clean_trivia_dataset_v0.csv"
data_path = project_root / "data" / "project_datasets" / name

print('Path to csv: ', data_path)

df = Trivia.load_dataset(name, str(data_path))

    