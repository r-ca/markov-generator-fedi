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

import requests

import markovify
import config

# Local application imports
from app.utils.helpers import format_bytes
from app.services.http_client import session as request_session
from app.services.background_processor import start_misskey_job, start_mastodon_job
from app.services.auth.base import get_provider

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

    if import_size < 1000 or import_size > 1000000:
        return make_response('import_size must be between 1000 and 1000000', 400)

    # generic session
    session.clear()
    session['import_size'] = import_size
    session['logged_in'] = False
    session.permanent = True
    session['hasModelData'] = False

    try:
        provider = get_provider(data['type'], request_session, request.host_url)
    except ValueError:
        return make_response('unsupported type', 400)

    try:
        redirect_url = provider.begin_login(data)
    except RuntimeError as e:
        return make_response(str(e), 500)

    return redirect(redirect_url)


@auth_bp.route('/login/callback')
def login_callback():
    if 'logged_in' not in session:
        return make_response(
            '<meta name="viewport" content="width=device-width">セッションデータが異常です。Cookieを有効にしているか確認の上再試行してください。<a href="/">トップページへ戻る</a>',
            400,
        )

    try:
        provider = get_provider(session['type'], request_session, request.host_url)
    except ValueError:
        return make_response('unsupported', 400)

    try:
        info = provider.complete_login(request.args)
    except RuntimeError as e:
        return make_response(str(e), 500)

    if session['type'] == 'misskey':
        thread_id = start_misskey_job(dict(session), info['token'])
    else:  # mastodon
        thread_id = start_mastodon_job(dict(session), info['token'], info['account'])

    session['logged_in'] = True
    return redirect('/job_wait?job_id=' + thread_id)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/') 
