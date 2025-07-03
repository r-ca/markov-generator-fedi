from __future__ import annotations

from typing import Dict, Any

import requests
import mastodon as mastodon_lib
from flask import session

from services.http_client import USER_AGENT
from .base import AuthProvider, register_provider


@register_provider('mastodon')
class MastodonAuthProvider(AuthProvider):
    """Mastodon OAuth authentication provider."""

    def begin_login(self, form_data: Dict[str, Any]) -> str:
        hostname = form_data['hostname'].lower()
        session['hostname'] = hostname
        session['type'] = 'mastodon'
        session['importVisibility'] = form_data.get('importVisibility', 'public_only')
        session['allowGenerateByOther'] = form_data.get('allowGenerateByOther', False)

        # create app
        options = {
            'client_name': 'markov-generator-fedi',
            'redirect_uris': f'{self.host_url}login/callback',
            'scopes': 'read write',
        }
        r = requests.post(f'https://{hostname}/api/v1/apps', json=options, headers={'User-Agent': USER_AGENT})
        if r.status_code != 200:
            raise RuntimeError(f'Failed to regist app: {r.text}')
        d = r.json()
        session['mstdn_app_key'] = d['client_id']
        session['mstdn_app_secret'] = d['client_secret']
        session['mstdn_redirect_uri'] = f'{self.host_url}login/callback'

        querys = {
            'client_id': d['client_id'],
            'response_type': 'code',
            'redirect_uri': f'{self.host_url}login/callback',
            'scopes': 'read write',
        }
        return f'https://{hostname}/oauth/authorize?{requests.utils.requote_uri(requests.compat.urlencode(querys))}'

    def complete_login(self, request_args: Dict[str, Any]) -> Dict[str, Any]:
        hostname = session['hostname']
        auth_code = request_args.get('code')
        if not auth_code:
            raise RuntimeError('<meta name="viewport" content="width=device-width">認証に失敗しました。')

        r = requests.post(
            f'https://{hostname}/oauth/token',
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
            raise RuntimeError(f'Failed to get token: {r.text}')
        token = r.json()['access_token']

        r = requests.get(
            f'https://{hostname}/api/v1/accounts/verify_credentials',
            headers={'Authorization': f'Bearer {token}', 'User-Agent': USER_AGENT},
        )
        if r.status_code != 200:
            raise RuntimeError(f'Failed to verify credentials: {r.text}')

        account = r.json()
        session['username'] = account['username']
        session['acct'] = f"{session['username']}@{hostname}"
        return {'token': token, 'account': account} 
