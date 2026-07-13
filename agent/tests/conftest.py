"""Make the test-support module importable regardless of pytest's rootdir."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
