from __future__ import annotations

import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Resolve configuration with env vars > config.py defaults
    try:
        import config  # noqa: WPS433

        PORT = int(os.environ.get('PORT', getattr(config, 'PORT', 8888)))
        HOST = os.environ.get('HOST', getattr(config, 'HOST', '127.0.0.1'))
        DEBUG = os.environ.get('DEBUG', str(getattr(config, 'DEBUG', True))).lower() in ('true', '1', 'yes')
    except ModuleNotFoundError:
        PORT = int(os.environ.get('PORT', 8888))
        HOST = os.environ.get('HOST', '127.0.0.1')
        DEBUG = os.environ.get('DEBUG', 'true').lower() in ('true', '1', 'yes')

    app.run(host=HOST, port=PORT, debug=DEBUG, threaded=True) 
