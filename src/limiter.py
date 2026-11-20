"""
SecureDoc AI — Rate Limiting Configuration
Prevents DoS attacks and API quota abuse using slowapi.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
