"""Create real UI previews without accessing the interactive desktop."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_demo import render

render(sys.argv[1])
print("Rendered actual Qt widgets offscreen with synthetic data; Steam was not contacted.")
