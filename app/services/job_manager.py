import threading
import traceback
from datetime import datetime
from datetime import timedelta
from typing import Dict, Any

__all__ = [
    'job_status',
    'cleanup_completed_jobs',
]

# Shared job status dictionary (previously global in web.py)
job_status: dict[str, dict] = {}

# ジョブの最大保持時間（秒）
MAX_JOB_AGE = timedelta(hours=1)  # 1時間


def _proc_error_hook(args):  # type: ignore[param-type]
    """Threading exception hook that records unexpected thread errors."""
    print(''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))
    job_status[args.thread.name] = {
        'completed': True,
        'error': (
            'スレッドが異常終了しました<br>'
            f'<strong>{args.exc_type.__name__}</strong>'
            f'<div>{str(args.exc_value)}</div>'
        ),
        'completed_at': datetime.now(),
    }


def cleanup_completed_jobs():
    """完了したジョブを一定時間後に削除する"""
    current_time = datetime.now()
    jobs_to_remove = []

    for job_id, job_info in job_status.items():
        if job_info.get('completed'):
            completed_at = job_info.get('completed_at', 0)
            if current_time - completed_at > MAX_JOB_AGE:
                jobs_to_remove.append(job_id)

    for job_id in jobs_to_remove:
        job_status.pop(job_id, None)


# Register as default exception hook for all new threads
threading.excepthook = _proc_error_hook
