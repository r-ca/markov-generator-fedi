# app/services/

ビジネスロジック / ドメインロジックを集約する層です。

| ディレクトリ / ファイル | 役割 |
|------------------------|-----------------------------------------|
| `auth/`                | 認証プロバイダ (`Misskey`, `Mastodon`) |
| `data_import/`         | 投稿取得インポータ (同上)              |
| `background_processor.py` | モデル学習スレッドを起動             |
| `job_manager.py`       | ジョブ状態の共有・例外フック           |
| `http_client.py`       | 共通 `requests.Session` + UA            |

### 共通化戦略
* **抽象基底クラス**で実装を差し替え可能 (`auth.base.AuthProvider`, `data_import.base.DataImporter`)
* 外部 API との通信はすべて `services/` 内で完結させ、routes からは呼び出すだけにする 
