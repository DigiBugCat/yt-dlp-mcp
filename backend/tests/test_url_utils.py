import pytest
from yt_dlp_mcp.utils.url import normalize_url, extract_youtube_video_id


# YouTube canonicalization
@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=abc123",
    "https://youtube.com/watch?v=abc123",
    "https://m.youtube.com/watch?v=abc123",
    "https://youtu.be/abc123",
    "https://youtube.com/watch?v=abc123&t=30",
    "https://youtube.com/watch?v=abc123&si=xyz123",
    "https://youtube.com/watch?v=abc123&list=PLfoo&index=3",
    "https://youtube.com/watch?v=abc123&feature=youtu.be",
    "https://youtu.be/abc123?t=30&si=xyz",
    "https://youtube.com/shorts/abc123",
    "https://youtube.com/embed/abc123",
    "https://youtube.com/v/abc123",
    "https://www.youtube.com/live/abc123",
    "https://www.youtube.com/live/abc123?si=xyz123",
    "https://youtube.com/live/abc123",
])
def test_youtube_canonical(url: str) -> None:
    assert normalize_url(url) == "https://youtube.com/watch?v=abc123"


def test_normalize_url_adds_scheme() -> None:
    assert normalize_url("youtube.com/watch?v=abc123") == "https://youtube.com/watch?v=abc123"


# Non-YouTube: generic normalization
def test_generic_strips_www() -> None:
    value = normalize_url("https://www.example.com/path?b=2&a=1")
    assert value == "https://example.com/path?a=1&b=2"


def test_generic_strips_trailing_slash() -> None:
    assert normalize_url("https://example.com/path/") == "https://example.com/path"


# extract_youtube_video_id
def test_extract_video_id_watch() -> None:
    assert extract_youtube_video_id("https://youtube.com/watch?v=abc123") == "abc123"

def test_extract_video_id_live() -> None:
    assert extract_youtube_video_id("https://www.youtube.com/live/abc123?si=xyz") == "abc123"

def test_extract_video_id_non_youtube() -> None:
    assert extract_youtube_video_id("https://example.com/video/abc123") is None
