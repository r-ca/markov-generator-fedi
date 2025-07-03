import os
import sqlite3
from app.utils.helpers import dict_factory

__all__ = [
    'db',
    'get_db',
]

_db_path = os.environ.get('DB_PATH', 'markov.db')

# Single global connection reused across the app (equivalent to previous implementation)
db = sqlite3.connect(_db_path, check_same_thread=False)
# Return rows as dicts
# The helper comes from app.utils.helpers
db.row_factory = dict_factory

def get_db():
    """Return the shared SQLite connection used by the application."""
    return db 
