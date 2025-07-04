from __future__ import annotations

from flask import Blueprint, render_template, request, make_response, session

from app.services.job_manager import job_status, cleanup_completed_jobs

job_bp = Blueprint('job', __name__)


@job_bp.route('/error_test')
def error_test():
    """Simple route to render an error page for debugging."""
    return render_template('job_error.html', page_type='job', job={'error': request.args.get('text')})


@job_bp.route('/job_wait')
def job_wait():
    """Poll the status of a background job and show progress / result."""
    # 定期的にクリーンアップを実行
    cleanup_completed_jobs()
    
    job_id = request.args.get('job_id')
    if not job_id:
        return make_response('<meta name="viewport" content="width=device-width">Invaild job id', 400)

    if job_id not in job_status:
        return render_template('job_not_found.html', page_type='job')

    # Thread may have crashed
    job_info = job_status[job_id]

    if not job_info['completed']:
        thread = job_info.get('thread')
        if thread and not thread.is_alive():
            return make_response(render_template('job_error.html', page_type='job', message='スレッドが異常終了しました'), 500)
        return render_template('job_wait.html', page_type='job', d=job_info)

    # Handle completed job
    if job_info.get('error'):
        return make_response(render_template('job_error.html', page_type='job', message=job_info['error']), 500)

    # Success – remove job and show result
    session['hasModelData'] = True
    job = job_status.pop(job_id)
    return render_template('job_result.html', page_type='job', job=job) 
