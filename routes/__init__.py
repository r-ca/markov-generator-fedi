from flask import Blueprint

# Blueprints will be imported lazily to avoid circular imports

from .generate import generate_bp  # noqa: E402, F401

__all__ = [
    'generate_bp',
] 
