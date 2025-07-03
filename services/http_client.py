import requests

__all__ = [
    'USER_AGENT',
    'session',
]

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; Markov-Generator-Fedi) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# A single global session reused across the application
session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT}) 
