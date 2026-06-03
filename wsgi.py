"""Entry point for gunicorn / Render deployment."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from ats.app import app

if __name__ == "__main__":
    app.run()
