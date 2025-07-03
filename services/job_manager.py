import threading
import traceback

__all__ = [
    'job_status',
]

# Shared job status dictionary (previously global in web.py)
job_status: dict[str, dict] = {}


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
    }


# Register as default exception hook for all new threads
threading.excepthook = _proc_error_hook 
