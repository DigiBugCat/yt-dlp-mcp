from yt_dlp_mcp.utils.url import normalize_url


def test_normalize_url_basic() -> None:
    value = normalize_url("https://www.youtube.com/watch?v=abc123&feature=youtu.be")
    assert value == "https://youtube.com/watch?feature=youtu.be&v=abc123"


def test_normalize_url_adds_scheme() -> None:
    value = normalize_url("youtube.com/watch?v=abc123")
    assert value.startswith("https://")
