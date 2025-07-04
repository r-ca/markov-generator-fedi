from __future__ import annotations
import json
import os

from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def root():
    """Render landing page."""
    return render_template('index.html', page_type='home')


@main_bp.route('/privacy')
def privacy_page():
    """Render privacy policy page."""
    return render_template('privacypolicy.html')


@main_bp.route('/contributors')
def contributors_page():
    """Render contributors page."""
    contributors_file = os.path.join(os.path.dirname(__file__), '..', 'static', 'contributors.json')
    
    try:
        with open(contributors_file, 'r', encoding='utf-8') as f:
            contributors_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        contributors_data = {
            "authors": [],
            "specialContributers": [],
            "contributers": []
        }
    
    return render_template('contributors.html', page_type='feature', contributors=contributors_data) 
