from __future__ import annotations

import math
import time
import uuid
import threading
import traceback
import re
from typing import Dict, Any

import mastodon as mastodon_lib  # rename to avoid name clash
from misskey import Misskey
from app.services.job_manager import job_status
from app.utils.helpers import format_text
from app.models.markov_model import create_markov_model_by_multiline
from app.models.database import db
from app.services.data_import.misskey import MisskeyDataImporter
from app.services.data_import.mastodon import MastodonDataImporter

__all__ = [
    'start_misskey_job',
    'start_mastodon_job',
]


def _new_thread_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Misskey
# ---------------------------------------------------------------------------

def start_misskey_job(session_data: Dict[str, Any], token: str) -> str:
    """Spin up a background job that trains a Markov model using Misskey notes.

    Parameters
    ----------
    session_data: Mapping[str, Any]
        The current user session (Flask session proxy OK).
    token: str
        Misskey user token.

    Returns
    -------
    str
        The generated job_id.
    """
    thread_id = _new_thread_id()

    # Initialise job status
    job_status[thread_id] = dict(
        completed=False,
        error=None,
        progress=1,
        progress_str='初期化中です',
    )

    import_visibility = session_data.get('importVisibility', 'public_only')
    allow_by_other = session_data.get('allowGenerateByOther', False)

    def proc(job_id: str, data: Dict[str, Any]):  # noqa: C901 – legacy complexity
        st = time.time()
        job_status[job_id]['progress'] = 20
        job_status[job_id]['progress_str'] = '投稿を取得しています...'

        importer = MisskeyDataImporter(session_data, token)
        lines, imported_notes = importer.fetch_lines()

        job_status[job_id]['progress_str'] = 'モデルを作成しています'
        job_status[job_id]['progress'] = 80

        try:
            text_model = create_markov_model_by_multiline(lines)
        except Exception as e:
            job_status[job_id] = dict(completed=True, error=str(e))
            return

        job_status[job_id]['progress_str'] = 'データベースに書き込み中です'
        job_status[job_id]['progress'] = 90

        try:
            cur = db.cursor()
            cur.execute('DELETE FROM model_data WHERE acct = ?', (data['acct'],))
            cur.execute(
                'INSERT INTO model_data(acct, data, allow_generate_by_other) VALUES (?, ?, ?)',
                (data['acct'], text_model.to_json(), int(allow_by_other == 'on')),
            )
            cur.close()
            db.commit()
        except Exception:
            traceback.print_exc()
            job_status[job_id] = dict(completed=True, error='Failed to save model')
            return

        job_status[job_id] = dict(
            completed=True,
            error=None,
            progress=100,
            progress_str='完了',
            result=f'取り込み済投稿数: {imported_notes}<br>処理時間: {(time.time() - st)*1000:.2f} ミリ秒',
        )

    thread = threading.Thread(
        target=proc,
        args=(
            thread_id,
            dict(
                hostname=session_data['hostname'],
                user_id=session_data['user_id'],
                acct=session_data['acct'],
                import_size=session_data['import_size'],
            ),
        ),
        name=thread_id,
    )
    thread.start()
    job_status[thread_id]['thread'] = thread
    return thread_id


# ---------------------------------------------------------------------------
# Mastodon
# ---------------------------------------------------------------------------

def start_mastodon_job(
    session_data: Dict[str, Any],
    token: str,
    account: dict,
) -> str:
    """Background job for Mastodon accounts."""
    thread_id = _new_thread_id()
    job_status[thread_id] = dict(
        completed=False,
        error=None,
        progress=1,
        progress_str='初期化中です',
    )

    import_visibility = session_data.get('importVisibility', 'public_only')
    allow_by_other = session_data.get('allowGenerateByOther', False)

    def proc(job_id: str, data: Dict[str, Any]):  # noqa: C901 – legacy complexity
        st = time.time()
        job_status[job_id]['progress'] = 20
        job_status[job_id]['progress_str'] = '投稿を取得しています。'

        importer = MastodonDataImporter(session_data, token, account)
        lines, imported_toots = importer.fetch_lines()

        job_status[job_id]['progress_str'] = 'モデルを作成しています'
        job_status[job_id]['progress'] = 80

        try:
            text_model = create_markov_model_by_multiline(lines)
        except Exception as e:
            job_status[job_id] = dict(completed=True, error='Failed to create model: ' + str(e))
            return

        job_status[job_id]['progress_str'] = 'データベースに書き込み中です'
        job_status[job_id]['progress'] = 90

        try:
            cur = db.cursor()
            cur.execute('DELETE FROM model_data WHERE acct = ?', (data['acct'],))
            cur.execute(
                'INSERT INTO model_data(acct, data, allow_generate_by_other) VALUES (?, ?, ?)',
                (data['acct'], text_model.to_json(), int(allow_by_other == 'on')),
            )
            cur.close()
            db.commit()
        except Exception:
            traceback.print_exc()
            job_status[job_id] = dict(completed=True, error='Failed to save model to database')
            return

        job_status[job_id] = dict(
            completed=True,
            error=None,
            progress=100,
            progress_str='完了',
            result=f'取り込み済投稿数: {imported_toots}<br>処理時間: {(time.time() - st)*1000:.2f} ミリ秒',
        )

    thread = threading.Thread(
        target=proc,
        args=(
            thread_id,
            dict(
                hostname=session_data['hostname'],
                mstdn_app_key=session_data['mstdn_app_key'],
                mstdn_app_secret=session_data['mstdn_app_secret'],
                acct=session_data['acct'],
                import_size=session_data['import_size'],
            ),
        ),
        name=thread_id,
    )
    thread.start()
    job_status[thread_id]['thread'] = thread
    return thread_id 
