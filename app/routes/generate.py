from __future__ import annotations

import html
import json
import urllib.parse
import time
import gc
import threading
from typing import Dict, Any, Optional

from flask import Blueprint, render_template, request, session, make_response

import markovify
import Levenshtein as levsh

from app.utils.helpers import format_text, format_bytes, get_memory_usage
from app.models.database import get_db_connection
from app.services.http_client import USER_AGENT

# Blueprint definition

generate_bp = Blueprint('generate', __name__)

# モデルキャッシュ（スレッドセーフ）
_model_cache: Dict[str, Any] = {}
_cache_lock = threading.Lock()
MAX_CACHE_SIZE = 5  # 最大キャッシュ数
CACHE_EXPIRY = 300  # キャッシュ有効期限（秒）


def _cleanup_expired_cache():
    """期限切れのキャッシュを削除する"""
    current_time = time.time()
    with _cache_lock:
        expired_keys = [
            key for key, value in _model_cache.items()
            if current_time - value['timestamp'] > CACHE_EXPIRY
        ]
        for key in expired_keys:
            del _model_cache[key]


def _get_cached_model(acct: str, model_data: str) -> Optional[markovify.Text]:
    """キャッシュからモデルを取得する"""
    _cleanup_expired_cache()
    with _cache_lock:
        if acct in _model_cache:
            return _model_cache[acct]['model']
    return None


def _cache_model(acct: str, model: markovify.Text, model_data: str):
    """モデルをキャッシュに保存する"""
    _cleanup_expired_cache()
    with _cache_lock:
        # キャッシュサイズを制限
        if len(_model_cache) >= MAX_CACHE_SIZE:
            # 最も古いエントリを削除
            oldest_key = min(_model_cache.keys(), key=lambda k: _model_cache[k]['timestamp'])
            del _model_cache[oldest_key]
        
        _model_cache[acct] = {
            'model': model,
            'data_hash': hash(model_data),
            'timestamp': time.time()
        }


def _should_use_cache(acct: str, model_data: str) -> bool:
    """キャッシュを使用すべきかどうかを判定する"""
    # 大きなモデル（1MB以上）の場合のみキャッシュを使用
    return len(model_data.encode()) > 1024 * 1024


@generate_bp.route('/generate')
def generate_page():
    """Render the generation form page."""
    return render_template('generate.html', page_type='feature', text=None, acct='', share_text='', up=urllib.parse)


@generate_bp.route('/generate/do', methods=['GET'])
def generate_do():
    """Generate a sentence from a trained Markov model."""
    query = request.args

    # ----- parse parameters -----
    min_words = 1
    if query.get('min_words') and query['min_words'].isdigit():
        min_words = int(query['min_words'])
        min_words = max(1, min(min_words, 50))

    startswith = ''
    if query.get('startswith'):
        startswith = query['startswith'].strip()[:10]

    # ----- choose target account -----
    if not query.get('acct'):
        # own data
        if not session.get('logged_in'):
            return render_template(
                'generate.html',
                page_type='feature',
                internal_error=True,
                internal_error_message='自分の投稿から文章を作るにはログインしてください <a href="/#loginModal">ログインする</a>',
                text='',
                splited_text=[],
                share_text='',
                min_words=min_words,
            )

        acct = session['acct'].lstrip('@')
    else:
        acct = query['acct'].lstrip('@')

    # ----- fetch model data -----
    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute('SELECT allow_generate_by_other, data FROM model_data WHERE acct = ?', (acct,))
        data = cur.fetchone()
        cur.close()
    except Exception as e:
        print(f"[ERROR] Database error in generate_do: {e}")
        return render_template(
            'generate.html',
            page_type='feature',
            internal_error=True,
            internal_error_message='データベースエラーが発生しました。しばらく時間をおいてから再試行してください。',
            text='',
            splited_text=[],
            acct=acct,
            share_text='',
            min_words=min_words,
        )

    if not data:
        return render_template(
            'generate.html',
            page_type='feature',
            internal_error=True,
            internal_error_message=f'{acct} の学習データは見つかりませんでした。',
            text='',
            splited_text=[],
            acct=acct,
            share_text='',
            min_words=min_words,
        )

    # permission check
    if session.get('acct') != acct and not bool(data['allow_generate_by_other']):
        return render_template(
            'generate.html',
            page_type='feature',
            internal_error=True,
            internal_error_message='このユーザーは他のユーザーからの文章生成を許可していません。',
            text='',
            splited_text=[],
            acct=acct,
            share_text='',
            min_words=min_words,
        )

    # メモリ使用量をログ出力
    try:
        memory_info = get_memory_usage()
        print(f"[GENERATE] START - RSS={memory_info['rss']}, VMS={memory_info['vms']}, Percent={memory_info['percent']:.1f}%")
    except Exception:
        pass

    # ----- build markov model -----
    text_model = None
    model_data = None
    use_cache = _should_use_cache(acct, data['data'])
    
    try:
        # キャッシュからモデルを取得を試行
        if use_cache:
            text_model = _get_cached_model(acct, data['data'])
        
        # キャッシュにない場合は新規作成
        if text_model is None:
            text_model = markovify.Text.from_json(data['data'])
            if use_cache:
                _cache_model(acct, text_model, data['data'])
        
        markov_params = dict(tries=100, min_words=min_words)

        st = time.perf_counter()
        sw_failed = False

        try:
            if startswith:
                gen_text = text_model.make_sentence_with_start(startswith, **markov_params)
            else:
                gen_text = text_model.make_sentence(**markov_params)
            if not gen_text:
                raise AttributeError
            text = gen_text.replace(' ', '')
            splited_text = ['<span class="badge bg-info">' + html.escape(t) + '</span>' for t in gen_text.split(' ')]
        except (AttributeError, markovify.text.ParamError, KeyError):
            text = None
            if startswith:
                sw_failed = True

        proc_time = (time.perf_counter() - st) * 1000  # ms

        # startswith failed suggestion
        sw_suggest = ''
        if sw_failed:
            # JSON データを一度だけ解析
            model_data = json.loads(data['data'])
            chain = json.loads(model_data['chain'])
            first_chains = list(chain[0][1].keys())
            word_lv_ratios = [dict(word=c, ratio=levsh.ratio(startswith, c)) for c in first_chains]
            word_lv_ratios.sort(key=lambda x: x['ratio'], reverse=True)
            sw_suggest = ' '.join([f'「{x["word"]}」' for x in word_lv_ratios[:5]])

        if not text:
            return render_template(
                'generate.html',
                page_type='feature',
                text='',
                splited_text=[],
                acct=acct,
                share_text='',
                min_words=min_words,
                failed=True,
                proc_time=proc_time,
                sw_failed=sw_failed,
                sw_suggest=sw_suggest,
            )

        share_text = (
            f'{text}\n\n`{acct}`\n#markov-generator-fedi\n{request.host_url}generate'
            f'?preset={urllib.parse.quote(acct)}&min_words={min_words}'
            + (f"&startswith={urllib.parse.quote(startswith)}" if startswith else '')
        )

        return render_template(
            'generate.html',
            page_type='feature',
            text=text,
            splited_text=splited_text,
            acct=acct,
            share_text=urllib.parse.quote(share_text),
            min_words=min_words,
            failed=False,
            proc_time=proc_time,
            model_data_size=format_bytes(len(data['data'].encode())),
        )

    except Exception as e:
        print(f"[ERROR] Exception in generate_do: {e}")
        return render_template(
            'generate.html',
            page_type='feature',
            internal_error=True,
            internal_error_message='文章生成中にエラーが発生しました。しばらく時間をおいてから再試行してください。',
            text='',
            splited_text=[],
            acct=acct,
            share_text='',
            min_words=min_words,
        )

    finally:
        # キャッシュを使用していない場合のみオブジェクトを解放
        if not use_cache and text_model is not None:
            del text_model
        if model_data is not None:
            del model_data
        
        # ガベージコレクションを強制実行
        gc.collect()
        
        # メモリ使用量をログ出力
        try:
            memory_info = get_memory_usage()
            print(f"[GENERATE] END - RSS={memory_info['rss']}, VMS={memory_info['vms']}, Percent={memory_info['percent']:.1f}%")
        except Exception:
            pass


@generate_bp.route('/my/delete-model-data', methods=['POST'])
def my_delete_model_data():
    """Delete current user's saved model data."""

    if not session.get('logged_in'):
        return make_response('Please login<br><a href="/">Top</a>', 401)

    if not session.get('acct'):
        return make_response('no acct', 400)

    if request.form.get('agreeDelete') != 'on':
        return 'Canceled.<br><a href="/">Top</a>'

    try:
        db = get_db_connection()
        cur = db.cursor()
        cur.execute('SELECT COUNT(*) as cnt FROM model_data WHERE acct = ?', (session['acct'],))
        res = cur.fetchone()
        cur.close()

        if not res or res['cnt'] == 0:
            return 'No data found<br><a href="/">Top</a>'

        cur = db.cursor()
        cur.execute('DELETE FROM model_data WHERE acct = ?', (session['acct'],))
        cur.close()
        db.commit()
    except Exception as e:
        print(f"[ERROR] Database error in delete_model_data: {e}")
        return 'Database error occurred<br><a href="/">Top</a>'

    session['hasModelData'] = False

    return 'Deleted successfully!<br><a href="/">Top</a>' 
