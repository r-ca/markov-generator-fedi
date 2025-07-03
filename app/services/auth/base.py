from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any

from flask import session, Request


class AuthProvider(ABC):
    """Base class for platform authentication providers."""

    def __init__(self, request_session, host_url: str):
        self.req_session = request_session
        self.host_url = host_url

    # -------------------- public API --------------------
    @abstractmethod
    def begin_login(self, form_data: Dict[str, Any]) -> str:
        """Start login process and return redirect URL."""

    @abstractmethod
    def complete_login(self, request_args: Dict[str, Any]) -> Dict[str, Any]:
        """Finish auth flow, update session, and return useful info

        Returns dict that may include tokens / account objects."""


# Provider registry -----------------------------------------------------------
_PROVIDER_MAP: Dict[str, type[AuthProvider]] = {}


def register_provider(name: str):
    """Decorator to register a provider class."""

    def decorator(cls: type[AuthProvider]):
        _PROVIDER_MAP[name] = cls
        return cls

    return decorator


def get_provider(name: str, request_session, host_url: str) -> AuthProvider:
    if name not in _PROVIDER_MAP:
        raise ValueError(f'Unknown auth provider: {name}')
    return _PROVIDER_MAP[name](request_session, host_url) 
