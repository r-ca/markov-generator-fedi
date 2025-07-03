from __future__ import annotations

import hashlib
import json
import math
import time
import urllib.parse
import uuid
import re
import traceback
import random
import threading

from datetime import timedelta

from flask import Blueprint, redirect, render_template, request, make_response, session

import mastodon
from misskey import Misskey, MiAuth, Permissions
from misskey.exceptions import MisskeyMiAuthFailedException

import requests

import markovify
import config

# Local application imports
from models.database import db
from models.markov_model import create_markov_model_by_multiline
from utils.helpers import format_text
from services.http_client import USER_AGENT, session as request_session
from services.job_manager import job_status

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.form
    if not data.get('type'):
        return make_response('type is required', 400)
    if not data.get('hostname'):
        return make_response('hostname is required', 400)
    if not data.get('import_size'):
        return make_response('import_size is required', 400)

    try:
        import_size = int(data['import_size'])
    except ValueError:
        return make_response('import_size is invalid', 400)

    if import_size < 1000 or import_size > 20000:
        return make_response('import_size must be between 1000 and 20000', 400)

    session['import_size'] = import_size

    # Common session flags
    session['logged_in'] = False
    session.permanent = True
    session['hostname'] = data['hostname'].lower()
    session['type'] = data['type']
    session['importVisibility'] = data.get('importVisibility', 'public_only')
    session['allowGenerateByOther'] = data.get('allowGenerateByOther', False)
    session['hasModelData'] = False

    if data['type'] == 'misskey':
        # ----- Misskey authentication -----
        try:
            mi = Misskey(address=data['hostname'], session=request_session)
        except requests.exceptions.ConnectionError:
            return make_response('<meta name="viewport" content="width=device-width">インスタンスと通信できませんでした。(ConnectionError)', 500)

        instance_info = mi.meta()

        if instance_info['features'].get('miauth') is True:
            miauth = MiAuth(
                address=data['hostname'],
                name='markov-generator-fedi',
                callback=f'{request.host_url}login/callback',
                permission=[Permissions.READ_ACCOUNT],
                session=request_session,
            )
            url = miauth.generate_url()
            session['session_id'] = miauth.session_id
            session['mi_legacy'] = False
            return redirect(url)
        # ----- legacy (< v12.39.1) -----
        options = {
            'name': 'markov-generator-fedi (Legacy)',
            'callback': f'{request.host_url}login/callback',
            'permission': ['read:account'],
            'description': 'Created by CyberRex (@cyberrex_v2@misskey.io)',
            'callbackUrl': f'{request.host_url}login/callback',
        }
        r = requests.post(
            f'https://{data["hostname"]}/api/app/create',
            json=options,
            headers={'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            return make_response(f'Failed to generate app: {r.text}', 500)
        j = r.json()

        secret_key = j['secret']
        r = requests.post(
            f'https://{data["hostname"]}/api/auth/session/generate',
            json={'appSecret': secret_key},
            headers={'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            return make_response(f'Failed to generate session: {r.text}', 500)
        j = r.json()

        session['mi_session_token'] = j['token']
        session['mi_secret_key'] = secret_key
        session['mi_legacy'] = True
        return redirect(j['url'])

    if data['type'] == 'mastodon':
        # ----- Mastodon authentication -----
        options = {
            'client_name': 'markov-generator-fedi',
            'redirect_uris': f'{request.host_url}login/callback',
            'scopes': 'read write',
        }
        r = requests.post(
            f'https://{data["hostname"]}/api/v1/apps',
            json=options,
            headers={'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            return make_response(f'Failed to regist app: {r.text}', 500)

        d = r.json()
        session['mstdn_app_key'] = d['client_id']
        session['mstdn_app_secret'] = d['client_secret']
        session['mstdn_redirect_uri'] = f'{request.host_url}login/callback'

        querys = {
            'client_id': d['client_id'],
            'response_type': 'code',
            'redirect_uri': f'{request.host_url}login/callback',
            'scopes': 'read write',
        }
        return redirect(f'https://{data["hostname"]}/oauth/authorize?{urllib.parse.urlencode(querys)}')

    return 'How did you come to here'


@auth_bp.route('/login/callback')
def login_callback():
    if 'logged_in' not in session:
        return make_response(
            '<meta name="viewport" content="width=device-width">セッションデータが異常です。Cookieを有効にしているか確認の上再試行してください。<a href="/">トップページへ戻る</a>',
            400,
        )

    if session['type'] == 'misskey':
        # ----- Misskey callback -----
        if not session['mi_legacy']:
            miauth = MiAuth(session['hostname'], session_id=session['session_id'], session=request_session)
            try:
                token = miauth.check()
            except MisskeyMiAuthFailedException:
                session.clear()
                return make_response('<meta name="viewport" content="width=device-width">認証に失敗しました。', 500)
            session['token'] = token
        else:
            secret_key = session['mi_secret_key']
            session_token = session['mi_session_token']
            r = requests.post(
                f'https://{session["hostname"]}/api/auth/session/userkey',
                json={'appSecret': secret_key, 'token': session_token},
                headers={'User-Agent': USER_AGENT},
            )
            if r.status_code != 200:
                return make_response(f'Failed to generate session: {r.text}', 500)
            j = r.json()
            access_token = j['accessToken']
            ccStr = f'{access_token}{secret_key}'
            token = hashlib.sha256(ccStr.encode('utf-8')).hexdigest()

        mi: Misskey = Misskey(address=session['hostname'], i=token, session=request_session)
        i = mi.i()

        session['username'] = i['username']
        session['acct'] = f"{i['username']}@{session['hostname']}"
        session['user_id'] = i['id']

        thread_id = str(uuid.uuid4())
        job_status[thread_id] = {
            'completed': False,
            'error': None,
            'progress': 1,
            'progress_str': '初期化中です',
        }

        importVisibility = session['importVisibility']
        allowGenerateByOther = session['allowGenerateByOther']

        # ---------------- background worker ----------------
        def proc(job_id, data):  # noqa: C901  (keep legacy complexity)
            st = time.time()
            job_status[job_id]['progress'] = 20
            job_status[job_id]['progress_str'] = '投稿を取得しています...'

            notes: list[dict] = []
            kwargs = {}
            withfiles = False
            mi2: Misskey = Misskey(address=data['hostname'], i=token, session=request_session)
            userdata_block = mi2.users_show(user_id=data['user_id'])
            took_time_array: list[float] = []

            for i_ in range(int(data['import_size'] / 100) + 1):
                t = time.time()
                notes_block = mi2.users_notes(
                    data['user_id'],
                    include_replies=False,
                    include_my_renotes=False,
                    with_files=withfiles,
                    limit=100,
                    **kwargs,
                )
                if not notes_block:
                    if not withfiles:
                        withfiles = True
                        continue
                    break
                kwargs['until_id'] = notes_block[-1]['id']
                for note in notes_block:
                    visibility = note['visibility']
                    if importVisibility == 'public_only':
                        if visibility not in ('public', 'home'):
                            continue
                    elif importVisibility == 'followers' and visibility == 'specified':
                        continue
                    notes.append(note)

                # progress calc
                try:
                    job_status[job_id]['progress'] = 20 + (
                        (i_ / (int(userdata_block['notesCount']) / 100)) * 60
                    )
                except ZeroDivisionError:
                    job_status[job_id]['progress'] = 50

                # ETA calc
                if took_time_array:
                    avg_took_time = sum(took_time_array) / len(took_time_array)
                    est = avg_took_time * ((int(userdata_block['notesCount']) / 100) - i_)
                    est_min = math.floor(est / 60)
                    est_sec = math.floor(est % 60)
                    job_status[job_id]['progress_str'] = f'投稿を取得しています。 (残 {str(est_min) + "分" if est_min > 0 else ""}{est_sec}秒)'
                took_time_array.append(time.time() - t)

            # -------- model build --------
            lines: list[str] = []
            for note in notes:
                if note['text'] and len(note['text']) > 2:
                    for l in note['text'].splitlines():
                        lines.append(format_text(l))

            job_status[job_id]['progress_str'] = 'モデルを作成しています'
            job_status[job_id]['progress'] = 80

            try:
                text_model = create_markov_model_by_multiline(lines)
            except Exception as e:
                job_status[job_id] = {
                    'completed': True,
                    'error': str(e),
                }
                return

            job_status[job_id]['progress_str'] = 'データベースに書き込み中です'
            job_status[job_id]['progress'] = 90

            try:
                cur = db.cursor()
                cur.execute('DELETE FROM model_data WHERE acct = ?', (data['acct'],))
                cur.execute(
                    'INSERT INTO model_data(acct, data, allow_generate_by_other) VALUES (?, ?, ?)',
                    (data['acct'], text_model.to_json(), int(allowGenerateByOther == 'on')),
                )
                cur.close()
                db.commit()
            except Exception:
                traceback.print_exc()
                job_status[job_id] = {
                    'completed': True,
                    'error': 'Failed to save model',
                }
                return

            job_status[job_id] = {
                'completed': True,
                'error': None,
                'progress': 100,
                'progress_str': '完了',
                'result': f'取り込み済投稿数: {len(notes)}<br>処理時間: {(time.time() - st) * 1000:.2f} ミリ秒',
            }

        thread = threading.Thread(
            target=proc,
            args=(
                thread_id,
                {
                    'hostname': session['hostname'],
                    'token': token,
                    'acct': session['acct'],
                    'user_id': session['user_id'],
                    'import_size': session['import_size'],
                },
            ),
            name=thread_id,
        )
        thread.start()

        job_status[thread_id]['thread'] = thread
        session['logged_in'] = True
        return redirect('/job_wait?job_id=' + thread_id)

    if session['type'] == 'mastodon':
        # ----- Mastodon callback -----
        auth_code = request.args.get('code')
        if not auth_code:
            return make_response('<meta name="viewport" content="width=device-width">認証に失敗しました。', 500)

        r = requests.post(
            f'https://{session["hostname"]}/oauth/token',
            json={
                'grant_type': 'authorization_code',
                'client_id': session['mstdn_app_key'],
                'client_secret': session['mstdn_app_secret'],
                'redirect_uri': session['mstdn_redirect_uri'],
                'scope': 'read write',
                'code': auth_code,
            },
            headers={'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            return make_response(f'Failed to get token: {r.text}', 500)
        d = r.json()
        token = d['access_token']

        r = requests.get(
            'https://' + session['hostname'] + '/api/v1/accounts/verify_credentials',
            headers={'Authorization': f'Bearer {token}', 'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            return make_response(f'Failed to verify credentials: {r.text}', 500)
        account = r.json()

        session['username'] = account['username']
        session['acct'] = f"{session['username']}@{session['hostname']}"

        thread_id = str(uuid.uuid4())
        job_status[thread_id] = {
            'completed': False,
            'error': None,
            'progress': 1,
            'progress_str': '初期化中です',
            'thread': None,
        }

        importVisibility = session['importVisibility']
        allowGenerateByOther = session['allowGenerateByOther']

        def proc(job_id, data):  # noqa: C901
            st = time.time()
            job_status[job_id]['progress'] = 20
            job_status[job_id]['progress_str'] = '投稿を取得しています。'

            mstdn = mastodon.Mastodon(
                client_id=data['mstdn_app_key'],
                client_secret=data['mstdn_app_secret'],
                access_token=token,
                api_base_url=f'https://{data['hostname']}',
                session=request_session,
            )

            toots = []
            last_id = None
            for i_ in range(int(data['import_size'] / 40) + 1):
                tmptoots = mstdn.account_statuses(account['id'], limit=40, max_id=last_id, exclude_reblogs=True)
                if not tmptoots:
                    break
                toots.extend(tmptoots)
                last_id = tmptoots[-1]

            job_status[job_id]['progress'] = 50

            # text processing
            lines: list[str] = []
            imported_toots = 0
            for toot in toots:
                visibility = toot['visibility']
                if importVisibility == 'public_only' and visibility not in ('public', 'unlisted'):
                    continue
                if importVisibility == 'followers' and visibility == 'direct':
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
                job_status[job_id] = {
                    'completed': True,
                    'error': 'Failed to create model: ' + str(e),
                }
                return

            job_status[job_id]['progress_str'] = 'データベースに書き込み中です'
            job_status[job_id]['progress'] = 90

            try:
                cur = db.cursor()
                cur.execute('DELETE FROM model_data WHERE acct = ?', (data['acct'],))
                cur.execute(
                    'INSERT INTO model_data(acct, data, allow_generate_by_other) VALUES (?, ?, ?)',
                    (data['acct'], text_model.to_json(), int(allowGenerateByOther == 'on')),
                )
                cur.close()
                db.commit()
            except Exception:
                traceback.print_exc()
                job_status[job_id] = {
                    'completed': True,
                    'error': 'Failed to save model to database',
                }
                return

            job_status[job_id] = {
                'completed': True,
                'error': None,
                'progress': 100,
                'progress_str': '完了',
                'result': f'取り込み済投稿数: {imported_toots}<br>処理時間: {(time.time() - st) * 1000:.2f} ミリ秒',
            }

        thread = threading.Thread(
            target=proc,
            args=(
                thread_id,
                {
                    'hostname': session['hostname'],
                    'mstdn_app_key': session['mstdn_app_key'],
                    'mstdn_app_secret': session['mstdn_app_secret'],
                    'acct': session['acct'],
                    'import_size': session['import_size'],
                },
            ),
            name=thread_id,
        )
        thread.start()

        job_status[thread_id]['thread'] = thread
        session['logged_in'] = True
        return redirect('/job_wait?job_id=' + thread_id)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/') 
