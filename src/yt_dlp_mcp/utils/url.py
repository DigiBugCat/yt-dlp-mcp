from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{url.strip()}")

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    query_pairs = [(k, v) for (k, v) in parse_qsl(parsed.query, keep_blank_values=False)]
    query = urlencode(sorted(query_pairs))

    return urlunparse((scheme, netloc, parsed.path.rstrip("/"), "", query, ""))
