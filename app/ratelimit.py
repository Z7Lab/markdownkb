"""Rate limiting configuration.

Disabled by default. Enable via the 'rate_limiting' feature flag in settings.
Useful when deploying as a shared platform or to prevent runaway LLM API costs.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, enabled=False)

# Rate limit tiers
STANDARD = "60/minute"
LLM = "10/minute"
HEAVY = "20/minute"
INDEXING = "5/minute"
