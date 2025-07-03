from __future__ import annotations

import re
from typing import List, Tuple

import mastodon as mastodon_lib

from app.utils.helpers import format_text
from .base import DataImporter

__all__ = ['MastodonDataImporter']


class MastodonDataImporter(DataImporter):
    def __init__(self, session_data, token: str, account: dict):
        super().__init__(session_data)
        self.token = token
        self.account = account
        self.mstdn = mastodon_lib.Mastodon(
            client_id=session_data['mstdn_app_key'],
            client_secret=session_data['mstdn_app_secret'],
            access_token=token,
            api_base_url=f"https://{session_data['hostname']}",
        )

    def fetch_lines(self) -> Tuple[List[str], int]:
        toots: List[dict] = []
        last_id = None
        for _ in range(int(self.session_data['import_size'] / 40) + 1):
            block = self.mstdn.account_statuses(self.account['id'], limit=40, max_id=last_id, exclude_reblogs=True)
            if not block:
                break
            toots.extend(block)
            last_id = block[-1]

        lines: List[str] = []
        imported = 0
        for toot in toots:
            if not self._format_visibility_filter(toot['visibility']):
                continue
            imported += 1
            if toot['content'] and len(toot['content']) > 2:
                for l in toot['content'].splitlines():
                    tx = re.sub(r'<[^>]*>', '', l)
                    lines.append(format_text(tx))
        return lines, imported 
