from photowalk.constants import PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


def test_photo_extensions_is_set():
    assert isinstance(PHOTO_EXTENSIONS, set)
    assert ".jpg" in PHOTO_EXTENSIONS
    assert ".jpeg" in PHOTO_EXTENSIONS


def test_video_extensions_is_set():
    assert isinstance(VIDEO_EXTENSIONS, set)
    assert ".mp4" in VIDEO_EXTENSIONS
    assert ".mov" in VIDEO_EXTENSIONS
