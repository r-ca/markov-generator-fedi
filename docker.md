# Docker使用方法

Dockerを使って簡単に立ち上げる方法

## 起動方法

```bash
# ビルドして起動
docker compose up --build

# バックグラウンドで起動
docker compose up --build -d

# 停止
docker compose down
```

## アクセス

アプリケーションは http://localhost:8888 でアクセスできます。

## データの永続化

- データベースは **ネームドボリューム** `markov_data` に保存され、コンテナを再起動してもデータは保持されます
- 初回起動時にデータベースが自動作成されます

## カスタム設定（オプション）

### 環境変数での設定（推奨）

最も簡単な設定方法です。`compose.yaml`の`environment`セクションを編集してください。

```yaml
environment:
  # アプリ設定のカスタマイズ例
  - PORT=8080          # ポート変更
  - DEBUG=true         # デバッグモード有効
```

設定後は再ビルド・起動：

```bash
docker compose up --build
```

### config.pyを使用したカスタマイズ

デフォルト設定で問題ない場合は、この手順は不要です。特別な設定が必要な場合のみ実行してください。

1. プロジェクトルートに`config.py`を作成：

```python
# config.py
PORT = 8888  # ポート番号
HOST = '0.0.0.0'  # ホスト（Dockerでは0.0.0.0固定推奨）
DEBUG = False  # デバッグモード
MECAB_DICDIR = '/usr/local/lib/python3.13/site-packages/unidic/dicdir'  # MeCab辞書パス
MECAB_RC = '/etc/mecabrc'  # MeCabリソースファイル
```

2. `compose.yaml`の該当行のコメントアウトを外す：

```yaml
volumes:
  - ./markov_data:/app/data
  - ./config.py:/app/config.py:ro  # この行のコメントを外す
```

3. 再ビルド・起動：

```bash
docker compose up --build
```

### ネームドボリュームの管理

```bash
# ボリューム一覧を表示
docker volume ls

# データを完全に削除したい場合（注意！）
docker compose down -v

# ボリュームの場所を確認
docker volume inspect markov-generator-fedi_markov_data
```
