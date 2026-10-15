import os
import sys

# Ensure repository root is in Python module search path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

# Import the WSGI app instance from app.py
from app import app, init_db

# Auto-initialize database on serverless cold-start
try:
    init_db()
except Exception:
    pass

# Expose WSGI application handler for Vercel
app = app
