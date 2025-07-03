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
from services.background_processor import start_misskey_job, start_mastodon_job

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

        thread_id = start_misskey_job(session, token)
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

        thread_id = start_mastodon_job(session, token, account)
        session['logged_in'] = True
        return redirect('/job_wait?job_id=' + thread_id)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/') 
