"""Ensure the project root is importable so tests can ``import app...`` and
``import tests...`` regardless of the working directory pytest is invoked from.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))