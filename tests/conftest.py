"""Put `src/` on the import path so tests run without an editable install.

The repo targets Python >=3.10 (pyproject). Note the macOS system interpreter
is 3.9, which cannot even import these modules; use `python3.13 -m pytest`.
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
