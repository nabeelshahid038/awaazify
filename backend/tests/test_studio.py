from app.api.v1.studio import youtube_video_id


def test_youtube_video_id_supported_urls():
    expected = "dQw4w9WgXcQ"
    assert youtube_video_id(f"https://www.youtube.com/watch?v={expected}") == expected
    assert youtube_video_id(f"https://youtu.be/{expected}?si=test") == expected
    assert youtube_video_id(f"https://youtube.com/shorts/{expected}") == expected


def test_youtube_video_id_rejects_untrusted_or_invalid_urls():
    assert youtube_video_id("https://example.com/watch?v=dQw4w9WgXcQ") is None
    assert youtube_video_id("https://youtube.com/watch?v=short") is None
    assert youtube_video_id("not a url") is None
