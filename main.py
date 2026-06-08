import os
import sys

# Ensure src/ is in the python path so modules inside it can be imported directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from main import main as run_app

if __name__ == "__main__":
    run_app()
