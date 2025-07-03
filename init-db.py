import sqlite3, os

db_path = os.environ.get('DB_PATH', 'markov.db')

try:
    os.remove(db_path)
except PermissionError:
    print(f'Cannot remove {db_path} because file is in use or no permission.')
except Exception as e:
    print(f'Cannot remove {db_path}: {e!r}')
    pass

db = sqlite3.connect(db_path)

print('Initalizing database...', end='')

cur = db.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS model_data (acct TEXT NOT NULL PRIMARY KEY UNIQUE, data TEXT NOT NULL, allow_generate_by_other INTEGER NOT NULL)')
cur.close()

db.commit()
db.close()

print('OK')