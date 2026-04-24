"""SSRF-prevention validation for user-supplied URLs."""

import ipaddress
from urllib.parse import urlparse


# IPs that must never be reached via user-supplied URLs
_BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("169.254.0.0/16"),     # AWS/cloud metadata
    ipaddress.ip_network("100.100.100.0/24"),    # Alibaba metadata
    ipaddress.ip_network("fd00::/8"),             # ULA IPv6
    ipaddress.ip_network("fe80::/10"),            # Link-local IPv6
]

_BLOCKED_HOSTNAMES = frozenset({
    "metadata.google.internal",
    "metadata.goog",
})


def validate_api_base(url: str) -> str:
    """Validate an api_base URL is safe for outbound requests.

    Blocks non-HTTP schemes, cloud metadata endpoints, and
    obviously dangerous targets. Returns the URL unchanged if valid,
    raises ValueError otherwise.
    """
    if not url:
        return url

    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"api_base must use http or https scheme, got '{parsed.scheme}'")

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        raise ValueError("api_base has no hostname")

    if hostname in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Requests to {hostname} are not allowed")

    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_IP_NETWORKS:
            if addr in network:
                raise ValueError(f"Requests to {hostname} are not allowed (blocked IP range)")
    except ValueError as e:
        if "not allowed" in str(e):
            raise

    return url
