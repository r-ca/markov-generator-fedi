from __future__ import annotations

import math
import time
import gc
from typing import List, Tuple

from misskey import Misskey
from app.utils.helpers import format_text
from .base import DataImporter
from app.services.job_manager import job_status  # type: ignore

__all__ = ['MisskeyDataImporter']


class MisskeyDataImporter(DataImporter):
    def __init__(self, session_data, token: str, job_id: str = None):
        super().__init__(session_data)
        self.token = token
        self.mi = Misskey(address=session_data['hostname'], i=token)
        self.job_id = job_id

    def fetch_lines(self) -> Tuple[List[str], int]:
        # NOTE: progress updating is optional; handled by background_processor
        lines: List[str] = []
        imported_count = 0
        kwargs = {}
        with_files = False

        # fetch user meta for total count
        user_block = self.mi.users_show(user_id=self.session_data['user_id'])
        total = int(user_block.get('notesCount', 0))
        target_size = min(int(self.session_data['import_size']), total)

        # 進捗更新のための初期設定
        if self.job_id and self.job_id in job_status:
            job_status[self.job_id]['progress'] = 15
            job_status[self.job_id]['progress_str'] = f'投稿を取得しています... (0/{target_size}件)'

        for i in range(int(self.session_data['import_size'] / 100) + 1):
            notes_block = self.mi.users_notes(
                self.session_data['user_id'],
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
            
            # 各ブロックを即座に処理してメモリを解放
            for note in notes_block:
                if not self._format_visibility_filter(note['visibility']):
                    continue
                
                if note.get('text') and len(note['text']) > 2:
                    for l in note['text'].splitlines():
                        lines.append(format_text(l))
                    imported_count += 1
            
            # 進捗を更新
            if self.job_id and self.job_id in job_status:
                progress_percent = min(15 + int((imported_count / target_size) * 65), 80)
                job_status[self.job_id]['progress'] = progress_percent
                job_status[self.job_id]['progress_str'] = f'投稿を取得しています... ({imported_count}/{target_size}件)'
            
            # ブロック処理後にメモリを解放
            del notes_block
            gc.collect()

        return lines, imported_count 
