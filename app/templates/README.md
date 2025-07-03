# app/templates/

Jinja2 テンプレートを格納します。ファイル名はエンドポイントに対応させると管理しやすくなります。

* 共通レイアウトが必要な場合は `base.html` を作り `{% extends 'base.html' %}` で継承してください。
* CSS / JS などは `app/static/` に置き、`url_for('static', filename='style.css')` で参照します。 
