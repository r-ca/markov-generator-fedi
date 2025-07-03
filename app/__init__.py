from __future__ import annotations

import os
import random
from datetime import timedelta

from flask import Flask

import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

# Local imports – routes must be imported after Flask instance is created
from app.utils.helpers import format_bytes  # noqa: F401 – keep a central import


def _init_sentry():
    """Initialise Sentry if SENTRY_DSN in config (silently ignore)."""
    try:
        import config  # noqa: WPS433

        dsn = getattr(config, 'SENTRY_DSN', None)
    except ModuleNotFoundError:
        dsn = None

    if not dsn:
        dsn = os.environ.get('SENTRY_DSN')
    if dsn:
        sentry_sdk.init(dsn=dsn, integrations=[FlaskIntegration()], traces_sample_rate=1.0)


def create_app() -> Flask:  # noqa: D401
    """Factory function for Flask app."""
    _init_sentry()

    app = Flask(__name__)

    # Secret key (32 random bytes)
    app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))
    app.permanent_session_lifetime = timedelta(hours=1)

    # Blueprint registrations (import locally to avoid circular refs)
    from app.routes import main_bp, generate_bp, job_bp, auth_bp  # noqa: WPS433,E402

    app.register_blueprint(main_bp)
    app.register_blueprint(generate_bp)
    app.register_blueprint(job_bp)
    app.register_blueprint(auth_bp)

    return app 
