from __future__ import annotations

import hashlib
from typing import Dict, Any

import requests
from misskey import Misskey, MiAuth, Permissions
from misskey.exceptions import MisskeyMiAuthFailedException

from flask import session

from app.services.http_client import USER_AGENT
from .base import AuthProvider, register_provider


@register_provider('misskey')
class MisskeyAuthProvider(AuthProvider):
    """Misskey authentication flow (MiAuth / legacy)."""

    def begin_login(self, form_data: Dict[str, Any]) -> str:  # noqa: D401
        hostname = form_data['hostname'].lower()
        session['hostname'] = hostname
        session['type'] = 'misskey'

        # Save import options
        session['importVisibility'] = form_data.get('importVisibility', 'public_only')
        session['allowGenerateByOther'] = form_data.get('allowGenerateByOther', False)

        # Detect if instance supports MiAuth
        try:
            mi = Misskey(address=hostname, session=self.req_session)
        except requests.exceptions.ConnectionError:
            raise RuntimeError('<meta name="viewport" content="width=device-width">インスタンスと通信できませんでした。(ConnectionError)')

        instance_info = mi.meta()
        if instance_info['features'].get('miauth') is True:
            miauth = MiAuth(
                address=hostname,
                name='markov-generator-fedi',
                callback=f'{self.host_url}login/callback',
                permission=[Permissions.READ_ACCOUNT],
                session=self.req_session,
            )
            url = miauth.generate_url()
            session['session_id'] = miauth.session_id
            session['mi_legacy'] = False
            return url

        # -------- legacy (< v12.39.1) --------
        options = {
            'name': 'markov-generator-fedi (Legacy)',
            'callback': f'{self.host_url}login/callback',
            'permission': ['read:account'],
            'description': 'Created by CyberRex (@cyberrex_v2@misskey.io)',
            'callbackUrl': f'{self.host_url}login/callback',
        }
        r = requests.post(
            f'https://{hostname}/api/app/create',
            json=options,
            headers={'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            raise RuntimeError(f'Failed to generate app: {r.text}')
        j = r.json()
        secret_key = j['secret']
        r = requests.post(
            f'https://{hostname}/api/auth/session/generate',
            json={'appSecret': secret_key},
            headers={'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            raise RuntimeError(f'Failed to generate session: {r.text}')
        j = r.json()
        session['mi_session_token'] = j['token']
        session['mi_secret_key'] = secret_key
        session['mi_legacy'] = True
        return j['url']

    def complete_login(self, request_args: Dict[str, Any]) -> Dict[str, Any]:
        hostname = session['hostname']
        if not session['mi_legacy']:
            miauth = MiAuth(hostname, session_id=session['session_id'], session=self.req_session)
            try:
                token = miauth.check()
            except MisskeyMiAuthFailedException:
                session.clear()
                raise RuntimeError('<meta name="viewport" content="width=device-width">認証に失敗しました。')
            session['token'] = token
        else:
            secret_key = session['mi_secret_key']
            session_token = session['mi_session_token']
            r = requests.post(
                f'https://{hostname}/api/auth/session/userkey',
                json={'appSecret': secret_key, 'token': session_token},
                headers={'User-Agent': USER_AGENT},
            )
            if r.status_code != 200:
                raise RuntimeError(f'Failed to generate session: {r.text}')
            access_token = r.json()['accessToken']
            token = hashlib.sha256(f'{access_token}{secret_key}'.encode('utf-8')).hexdigest()

        mi = Misskey(address=hostname, i=token, session=self.req_session)
        user_info = mi.i()
        session['username'] = user_info['username']
        session['acct'] = f"{user_info['username']}@{hostname}"
        session['user_id'] = user_info['id']
        return {'token': token} 
