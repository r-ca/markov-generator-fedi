import os
import sqlite3
import threading
import atexit
from app.utils.helpers import dict_factory

__all__ = [
    'db',
    'get_db',
    'get_db_connection',
    'close_db',
]

_db_path = os.environ.get('DB_PATH', 'markov.db')
_db_lock = threading.Lock()

# Single global connection reused across the app (equivalent to previous implementation)
db = sqlite3.connect(_db_path, check_same_thread=False, timeout=30.0)
# Return rows as dicts
# The helper comes from app.utils.helpers
db.row_factory = dict_factory

# WALモードを有効にして同時アクセス時のパフォーマンスを改善
try:
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA cache_size=10000")
    db.execute("PRAGMA temp_store=MEMORY")
except Exception as e:
    print(f"[WARNING] Failed to set SQLite optimizations: {e}")

def get_db():
    """Return the shared SQLite connection used by the application."""
    return db

def get_db_connection():
    """Get a thread-safe database connection."""
    with _db_lock:
        try:
            # 接続が有効かチェック
            db.execute("SELECT 1")
            return db
        except (sqlite3.OperationalError, sqlite3.InterfaceError):
            # 接続が無効な場合は再接続
            global db
            try:
                db.close()
            except:
                pass
            db = sqlite3.connect(_db_path, check_same_thread=False, timeout=30.0)
            db.row_factory = dict_factory
            
            # WALモードを再設定
            try:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA synchronous=NORMAL")
                db.execute("PRAGMA cache_size=10000")
                db.execute("PRAGMA temp_store=MEMORY")
            except Exception as e:
                print(f"[WARNING] Failed to set SQLite optimizations on reconnect: {e}")
            
            return db

def close_db():
    """Close the database connection."""
    global db
    try:
        if db:
            db.close()
            print("[INFO] Database connection closed")
    except Exception as e:
        print(f"[WARNING] Error closing database: {e}")

# アプリケーション終了時にデータベース接続を閉じる
atexit.register(close_db) 
