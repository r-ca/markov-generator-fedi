from flask import Blueprint

# Blueprints will be imported lazily to avoid circular imports

from .generate import generate_bp  # noqa: E402, F401
from .job import job_bp  # noqa: E402, F401
from .auth import auth_bp  # noqa: E402, F401
from .main import main_bp  # noqa: E402, F401

__all__ = [
    'generate_bp',
    'job_bp',
    'auth_bp',
    'main_bp',
] 
