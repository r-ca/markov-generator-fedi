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
from services.job_manager import job_status
from utils.helpers import format_text
from models.markov_model import create_markov_model_by_multiline
from models.database import db

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

        notes: list[dict] = []
        kwargs: dict = {}
        with_files = False
        mi2: Misskey = Misskey(address=data['hostname'], i=token)
        userdata_block = mi2.users_show(user_id=data['user_id'])
        took_time_array: list[float] = []

        total_blocks = int(data['import_size'] / 100) + 1
        for i_block in range(total_blocks):
            t0 = time.time()
            notes_block = mi2.users_notes(
                data['user_id'],
                include_replies=False,
                include_my_renotes=False,
                with_files=with_files,
                limit=100,
                **kwargs,
            )
            if not notes_block:
                if not with_files:
                    with_files = True
                    continue
                break

            kwargs['until_id'] = notes_block[-1]['id']
            for note in notes_block:
                vis = note['visibility']
                if import_visibility == 'public_only' and vis not in ('public', 'home'):
                    continue
                if import_visibility == 'followers' and vis == 'specified':
                    continue
                notes.append(note)

            # progress & ETA
            try:
                job_status[job_id]['progress'] = 20 + ((i_block / (int(userdata_block['notesCount']) / 100)) * 60)
            except ZeroDivisionError:
                job_status[job_id]['progress'] = 50

            if took_time_array:
                avg = sum(took_time_array) / len(took_time_array)
                est = avg * ((int(userdata_block['notesCount']) / 100) - i_block)
                job_status[job_id]['progress_str'] = (
                    '投稿を取得しています。 (残 '
                    f"{math.floor(est/60)}分{math.floor(est%60)}秒)"
                )
            took_time_array.append(time.time() - t0)

        # Build text list
        lines: list[str] = []
        for note in notes:
            if note.get('text') and len(note['text']) > 2:
                for l in note['text'].splitlines():
                    lines.append(format_text(l))

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
            result=f'取り込み済投稿数: {len(notes)}<br>処理時間: {(time.time() - st)*1000:.2f} ミリ秒',
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

        mstdn = mastodon_lib.Mastodon(
            client_id=data['mstdn_app_key'],
            client_secret=data['mstdn_app_secret'],
            access_token=token,
            api_base_url=f"https://{data['hostname']}",
        )

        toots: list[dict] = []
        last_id = None
        total_blocks = int(data['import_size'] / 40) + 1
        for _ in range(total_blocks):
            tmptoots = mstdn.account_statuses(account['id'], limit=40, max_id=last_id, exclude_reblogs=True)
            if not tmptoots:
                break
            toots.extend(tmptoots)
            last_id = tmptoots[-1]

        job_status[job_id]['progress'] = 50

        lines: list[str] = []
        imported_toots = 0
        for toot in toots:
            vis = toot['visibility']
            if import_visibility == 'public_only' and vis not in ('public', 'unlisted'):
                continue
            if import_visibility == 'followers' and vis == 'direct':
                continue
            imported_toots += 1
            if toot['content'] and len(toot['content']) > 2:
                for l in toot['content'].splitlines():
                    tx = re.sub(r'<[^>]*>', '', l)
                    lines.append(format_text(tx))

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
