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

- データベースは `markov_data/` フォルダに保存され、コンテナを再起動してもデータは保持されます
- 初回起動時にデータベースが自動作成されます

## カスタム設定（オプション）

特別な設定が必要な場合のみ、`config.py`を作成し、`compose.yaml`の該当行のコメントアウトを外してください。

## トラブルシューティング

```bash
# ログを確認
docker compose logs -f

# ポート変更が必要な場合（compose.yamlを編集）
ports:
  - "8889:8888"  # ホストの8889番ポートに変更
```
