"""Rate limiting configuration.

Disabled by default for local single-user installs.
Enable via the 'rate_limiting' core flag in settings when deploying on a
network-accessible host (MARKDOWNKB_HOST=0.0.0.0) to prevent LLM API cost
abuse and API-key brute-force attacks.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, enabled=False)

# Rate limit tiers
STANDARD = "60/minute"
LLM = "10/minute"
HEAVY = "20/minute"
INDEXING = "5/minute"
