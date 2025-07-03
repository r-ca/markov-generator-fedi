# app/

Flask アプリケーションのルートパッケージです。

* `__init__.py` … `create_app()` で Flask インスタンスを生成し、Blueprint を登録します。
* `run.py` … `python -m app.run` で開発サーバを起動できます。
* **ルート以外のモジュールは原則ここからの相対パスで import** してください。

```
from app.services.background_processor import start_misskey_job
```

## Blueprint 追加方法
1. `app/routes/xxx.py` に `xxx_bp = Blueprint('xxx', __name__)` を宣言
2. `app/routes/__init__.py` で `from .xxx import xxx_bp` を追加し `__all__` に含める
3. `create_app()` で自動 import された Blueprint が登録されます

## 設定
環境変数 > `config.py` の順で上書きされます。 
