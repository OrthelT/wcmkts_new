"""
Pytest configuration file for the wcmkts_refactor project.
This file sets up the Python path so tests can import modules from the project root.
"""
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
