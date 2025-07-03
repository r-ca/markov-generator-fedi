# app/routes/

各機能ごとの **Blueprint** を定義する層です。ファイル 1 つ = 1 Blueprint が基本方針です。

| ファイル | 役割 |
|---------|------|
| `main.py` | index, privacy など静的ページ |
| `generate.py` | モデル生成 UI / API |
| `job.py` | ジョブ進捗・エラーハンドラ |
| `auth.py` | 認証フロー (Misskey / Mastodon) |

新しい機能を追加するときは、同様に `xxx.py` を作成し、Blueprint をエクスポートしてください。

## 共通コーディング規約
* import は `from app.xxx` で統一
* ビジネスロジックは **services** 層へ委譲し、routes は薄く保つ
* Template は `render_template()` で `app/templates/` を参照 
