from __future__ import annotations

import re
import gc
from typing import List, Tuple

import mastodon as mastodon_lib

from app.utils.helpers import format_text
from .base import DataImporter
from app.services.job_manager import job_status  # type: ignore

__all__ = ['MastodonDataImporter']


class MastodonDataImporter(DataImporter):
    def __init__(self, session_data, token: str, account: dict, job_id: str = None):
        super().__init__(session_data)
        self.token = token
        self.account = account
        self.job_id = job_id
        self.mstdn = mastodon_lib.Mastodon(
            client_id=session_data['mstdn_app_key'],
            client_secret=session_data['mstdn_app_secret'],
            access_token=token,
            api_base_url=f"https://{session_data['hostname']}",
        )

    def fetch_lines(self) -> Tuple[List[str], int, int]:
        lines: List[str] = []
        imported = 0
        last_id = None
        target_size = int(self.session_data['import_size'])
        
        # 進捗更新のための初期設定
        if self.job_id and self.job_id in job_status:
            job_status[self.job_id]['progress'] = 15
            job_status[self.job_id]['progress_str'] = f'投稿を取得しています... (取得済み: 0件)'
        
        for i in range(int(self.session_data['import_size'] / 40) + 1):
            block = self.mstdn.account_statuses(self.account['id'], limit=40, max_id=last_id, exclude_reblogs=True)
            if not block:
                break
            
            # 各ブロックを即座に処理してメモリを解放
            for toot in block:
                if not self._format_visibility_filter(toot['visibility']):
                    continue
                
                if toot['content'] and len(toot['content']) > 2:
                    for l in toot['content'].splitlines():
                        tx = re.sub(r'<[^>]*>', '', l)
                        lines.append(format_text(tx))
                    imported += 1
            
            # 進捗を更新
            if self.job_id and self.job_id in job_status:
                progress_percent = min(15 + int((imported / target_size) * 65), 80) if target_size > 0 else min(15 + imported, 80)
                job_status[self.job_id]['progress'] = progress_percent
                job_status[self.job_id]['progress_str'] = f'投稿を取得しています... (取得済み: {imported}件)'
            
            last_id = block[-1]
            
            # ブロック処理後にメモリを解放
            del block
            gc.collect()
            
        return lines, imported, target_size 
