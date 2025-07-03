# Markov Generator Fedi

このリポジトリは Fediverse (Misskey / Mastodon) の投稿を取り込み、
マルコフ連鎖を用いて文章を生成するおもちゃアプリです。

## ディレクトリ構成 (抜粋)

```
app/                Flask アプリケーション本体
├── __init__.py     create_app() ファクトリ
├── run.py          ローカル実行エントリポイント
├── routes/         ルーティング(BP)層
├── services/       ビジネスロジック層
├── models/         DB・モデル層
├── utils/          共通ユーティリティ
├── templates/      Jinja2 テンプレート
└── static/         静的ファイル(任意)

docker-entrypoint.py  Docker 用エントリポイント
config.py             追加設定 (任意)
requirements.txt      依存ライブラリ
```

## セットアップ

```bash
python -m venv env && source env/bin/activate
pip install -U -r requirements.txt
python init-db.py          # 初回のみ DB 初期化
python -m app.run          # 開発サーバ起動
```

Docker で起動する場合は `docker-compose up -d`。

## 共通化戦略

* **Blueprint** でルートを分割 (`app/routes/`)
* **Service Layer** にビジネスロジックを集約 (`app/services/`)
* **Data Importer**/ **Auth Provider** を抽象基底クラスで拡張可能に
* テンプレートと静的ファイルは `app/` 配下に集約
* テストは `tests/` ディレクトリで pytest で実行

## テスト

```bash
pytest -q
```

## ライセンス

MIT 
