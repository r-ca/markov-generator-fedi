import re
import math
import html

__all__ = [
    'format_bytes',
    'dict_factory',
    'format_text',
]


def format_bytes(size: int) -> str:
    """Convert bytes to human-readable string (B, KB, MB, …).

    Parameters
    ----------
    size: int
        Size in bytes.

    Returns
    -------
    str
        Formatted string such as "10 KB".
    """
    power = 2 ** 10  # 1024
    n = 0
    power_labels = ['B', 'KB', 'MB', 'GB', 'TB']
    while size > power and n < len(power_labels) - 1:
        size /= power
        n += 1
    return '{:.0f} {}'.format(size, power_labels[n])


def dict_factory(cursor, row):
    """Convert SQLite rows to dicts keyed by column name."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


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
