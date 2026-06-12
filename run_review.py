#!/usr/bin/env python3
"""Run the QuestionReview Flask app."""
import os
import sys
from pathlib import Path

# Ensure project root is on path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from review_app.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=True)
