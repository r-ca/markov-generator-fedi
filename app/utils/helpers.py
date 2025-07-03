import re
import math
import html
import psutil
import os

__all__ = [
    'format_bytes',
    'dict_factory',
    'format_text',
    'get_memory_usage',
]


def format_bytes(bytes_value: int) -> str:
    """Format bytes into human readable string."""
    if bytes_value == 0:
        return "0 B"
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while bytes_value >= 1024 and i < len(size_names) - 1:
        bytes_value /= 1024.0
        i += 1
    return f"{bytes_value:.1f} {size_names[i]}"


def dict_factory(cursor, row):
    """Convert SQLite rows to dicts keyed by column name."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def get_memory_usage() -> dict:
    """Get current memory usage information."""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    return {
        'rss': format_bytes(memory_info.rss),  # Resident Set Size
        'vms': format_bytes(memory_info.vms),  # Virtual Memory Size
        'percent': process.memory_percent(),
        'available': format_bytes(psutil.virtual_memory().available),
        'total': format_bytes(psutil.virtual_memory().total),
    }


def format_text(text: str) -> str:
    """Clean and normalise one piece of text for Markov chain training.

    Operations:
    1. Remove full-width spaces
    2. Insert newlines after "。" when appropriate
    3. Remove multiple spaces / newlines
    4. Strip URLs
    """
    text = text.replace('　', ' ')  # Full-width to half-width space

    text = re.sub(r'(.+。) (.+。)', r'\1 \2\n', text)
    text = re.sub(r'\n +', '\n', text)  # Spaces after newline
    text = re.sub(r'([。．！？…])\n」', r'\1」 \n', text)
    text = re.sub(r'\n +', '\n', text)
    text = re.sub(r'\n+', '\n', text).rstrip('\n')
    text = re.sub(r'\n +', '\n', text)

    # Remove URLs
    text = re.sub(r'(http|ftp|https):\/\/[^\s]+', '', text)
    return text 
