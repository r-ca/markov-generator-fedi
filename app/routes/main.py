from __future__ import annotations

from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def root():
    """Render landing page."""
    return render_template('index.html')


@main_bp.route('/privacy')
def privacy_page():
    """Render privacy policy page."""
    return render_template('privacypolicy.html') 
