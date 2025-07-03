#!/usr/bin/env python3
"""
Docker用のエントリーポイントスクリプト
1. DBファイルが存在しない場合は自動作成
2. web.pyを読み込んで127.0.0.1を0.0.0.0に変更してから実行
"""

import os
import subprocess
import runpy

# dataディレクトリが存在しない場合は作成
data_dir = 'data'
if not os.path.exists(data_dir):
    os.makedirs(data_dir)
    print('Data directory created.')

# DBファイルが存在しない場合は初期化
db_path = os.path.join(data_dir, 'markov.db')
if not os.path.exists(db_path):
    print('Database not found. Initializing...')
    # init-db.pyを修正してdataディレクトリ内にDBを作成
    env = os.environ.copy()
    env['DB_PATH'] = db_path
    subprocess.run(['python3', 'init-db.py'], env=env, check=True)
    print('Database initialized successfully!')
else:
    print('Database found.')

# DB_PATH環境変数を設定
os.environ['DB_PATH'] = db_path

# 新しいエントリポイントを実行
runpy.run_module('app.run', run_name='__main__')
