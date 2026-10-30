"""Render real public artwork with synthetic states, without a Steam session."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from public_preview import render

render(sys.argv[1])
