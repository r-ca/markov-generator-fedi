from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any


class DataImporter(ABC):
    """Abstract base class for platform-specific data importers."""

    def __init__(self, session_data: Dict[str, Any]):
        self.session_data = session_data

    @abstractmethod
    def fetch_lines(self) -> Tuple[List[str], int]:
        """Fetch user's posts and return pre-processed text lines.

        Returns
        -------
        Tuple[List[str], int]
            A tuple of (list of processed lines, original post count imported)"""

    # Utility helper that subclasses can use
    def _format_visibility_filter(self, visibility: str) -> bool:
        """Return True if the given post visibility should be included."""
        setting = self.session_data.get('importVisibility', 'public_only')
        if setting == 'public_only':
            return visibility in ('public', 'home', 'unlisted')
        if setting == 'followers':
            return visibility != 'specified' and visibility != 'direct'
        # 'direct' means include all
        return True 
