# app/models/

DB・モデル関連のコードをまとめます。

| ファイル | 役割 |
|---------|------|
| `database.py` | SQLite 共有コネクション (`get_db()`) |
| `markov_model.py` | マルコフモデル生成ヘルパ |

DB スキーマ変更がある場合は `init-db.py` を更新してください。 
