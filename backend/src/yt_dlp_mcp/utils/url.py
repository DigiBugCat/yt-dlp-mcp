from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# YouTube hostnames to canonicalize
_YT_HOSTNAMES = frozenset({"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"})

# Query params that identify a video vs. tracking/sharing noise
_YT_TRACKING_PARAMS = frozenset({"si", "pp", "feature", "ab_channel", "utm_source", "utm_medium", "utm_campaign"})


def _extract_youtube_video_id(parsed) -> str | None:
    netloc = parsed.netloc.lower()
    path = parsed.path

    if netloc == "youtu.be":
        return path.strip("/") or None

    # youtube.com, m.youtube.com, www.youtube.com
    clean_path = path.rstrip("/")
    if clean_path == "/watch":
        params = dict(parse_qsl(parsed.query, keep_blank_values=False))
        return params.get("v") or None
    for prefix in ("/shorts/", "/embed/", "/v/", "/live/"):
        if clean_path.startswith(prefix):
            return clean_path[len(prefix):].strip("/") or None
    return None


def extract_youtube_video_id(url: str) -> str | None:
    """Return the YouTube video ID from a URL, or None if not a YouTube video URL."""
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{url.strip()}")
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if netloc not in _YT_HOSTNAMES:
        return None
    return _extract_youtube_video_id(parsed)


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{url.strip()}")

    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # YouTube: canonicalize all video URL forms to https://youtube.com/watch?v=VIDEO_ID
    if netloc in _YT_HOSTNAMES:
        video_id = _extract_youtube_video_id(parsed)
        if video_id:
            return f"https://youtube.com/watch?v={video_id}"

    # Generic: lowercase scheme/host, strip trailing slash, sort query params
    scheme = parsed.scheme.lower()
    query_pairs = [(k, v) for (k, v) in parse_qsl(parsed.query, keep_blank_values=False)]
    query = urlencode(sorted(query_pairs))
    return urlunparse((scheme, netloc, parsed.path.rstrip("/"), "", query, ""))
