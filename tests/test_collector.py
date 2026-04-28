"""Tests for the collector module."""

from pathlib import Path

from photowalk.collector import collect_files


def test_collect_files_single_file(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.touch()
    result = collect_files([photo], recursive=False)
    assert result == [photo]


def test_collect_files_directory_non_recursive(tmp_path):
    (tmp_path / "a.jpg").touch()
    (tmp_path / "b.mp4").touch()
    (tmp_path / "c.txt").touch()
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "d.jpg").touch()

    result = collect_files([tmp_path], recursive=False)
    names = sorted(p.name for p in result)
    assert names == ["a.jpg", "b.mp4"]


def test_collect_files_directory_recursive(tmp_path):
    (tmp_path / "a.jpg").touch()
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.mp4").touch()

    result = collect_files([tmp_path], recursive=True)
    names = sorted(p.name for p in result)
    assert names == ["a.jpg", "b.mp4"]


def test_collect_files_filter_photos_only(tmp_path):
    (tmp_path / "a.jpg").touch()
    (tmp_path / "b.mp4").touch()
    (tmp_path / "c.png").touch()

    result = collect_files([tmp_path], recursive=False, include_videos=False)
    names = sorted(p.name for p in result)
    assert names == ["a.jpg", "c.png"]


def test_collect_files_filter_videos_only(tmp_path):
    (tmp_path / "a.jpg").touch()
    (tmp_path / "b.mp4").touch()
    (tmp_path / "c.mov").touch()

    result = collect_files([tmp_path], recursive=False, include_photos=False)
    names = sorted(p.name for p in result)
    assert names == ["b.mp4", "c.mov"]


def test_collect_files_empty_directory(tmp_path):
    result = collect_files([tmp_path], recursive=False)
    assert result == []


def test_collect_files_mixed_paths(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.touch()
    subdir = tmp_path / "videos"
    subdir.mkdir()
    (subdir / "clip.mp4").touch()

    result = collect_files([photo, subdir], recursive=True)
    names = sorted(p.name for p in result)
    assert names == ["clip.mp4", "photo.jpg"]
