import struct
import wave
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

from photowalk.offset_detector import extract_audio, OffsetDetectionError, _load_audio, find_audio_offset, detect_trim_offset


class TestExtractAudio:
    def test_calls_ffmpeg_correctly(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        expected_path = tmp_path / "audio.wav"

        with patch("photowalk.offset_detector.subprocess.run", return_value=mock_result) as mock_run:
            with patch("photowalk.offset_detector.tempfile.NamedTemporaryFile") as mock_ntf:
                mock_file = MagicMock()
                mock_file.name = str(expected_path)
                mock_file.close = MagicMock()
                mock_ntf.return_value = mock_file

                result = extract_audio(Path("/tmp/video.mp4"))

        assert result == expected_path
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-vn" in cmd
        assert "pcm_s16le" in cmd
        assert "-ar" in cmd
        assert "16000" in cmd
        assert "-ac" in cmd
        assert "1" in cmd
        assert str(expected_path) in cmd

    def test_ffmpeg_failure_raises_and_cleans_up(self, tmp_path):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "audio extract failed"

        expected_path = tmp_path / "audio.wav"

        with patch("photowalk.offset_detector.subprocess.run", return_value=mock_result):
            with patch("photowalk.offset_detector.tempfile.NamedTemporaryFile") as mock_ntf:
                mock_file = MagicMock()
                mock_file.name = str(expected_path)
                mock_file.close = MagicMock()
                mock_ntf.return_value = mock_file

                with pytest.raises(OffsetDetectionError, match="audio extract failed"):
                    extract_audio(Path("/tmp/video.mp4"))


class TestLoadAudio:
    def test_load_mono_16bit_wav(self, tmp_path):
        wav_path = tmp_path / "test.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            samples = struct.pack("<" + "h" * 3, 100, -200, 300)
            wf.writeframes(samples)

        arr, sr = _load_audio(wav_path)
        assert sr == 16000
        assert len(arr) == 3
        assert arr.dtype == np.float32
        assert arr[0] == 100.0
        assert arr[1] == -200.0
        assert arr[2] == 300.0


class TestFindAudioOffset:
    def test_detects_known_offset_with_noise(self):
        rng = np.random.default_rng(123)
        sample_rate = 16000
        original = rng.standard_normal(32000).astype(np.float32)

        start_sample = int(0.5 * sample_rate)
        trim_duration = 1
        trimmed = original[start_sample : start_sample + trim_duration * sample_rate]

        offset = find_audio_offset(original, trimmed, sample_rate)
        assert abs(offset - 0.5) < 0.01

    def test_low_confidence_raises(self):
        rng = np.random.default_rng(42)
        original = rng.standard_normal(16000).astype(np.float32)
        trimmed = rng.standard_normal(8000).astype(np.float32)

        with pytest.raises(OffsetDetectionError, match="reliably detect"):
            find_audio_offset(original, trimmed, 16000)

    def test_trimmed_longer_than_original_raises(self):
        original = np.ones(1000, dtype=np.float32)
        trimmed = np.ones(2000, dtype=np.float32)

        with pytest.raises(OffsetDetectionError, match="longer than original"):
            find_audio_offset(original, trimmed, 16000)


class TestDetectTrimOffset:
    def test_orchestrates_extraction_and_finds_offset(self, tmp_path):
        rng = np.random.default_rng(456)
        orig_wav = tmp_path / "orig.wav"
        trim_wav = tmp_path / "trim.wav"
        orig_wav.write_text("dummy")
        trim_wav.write_text("dummy")

        original = rng.standard_normal(32000).astype(np.float32)
        start_sample = int(0.5 * 16000)
        trimmed = original[start_sample : start_sample + 16000]

        with patch("photowalk.offset_detector.extract_audio", side_effect=[orig_wav, trim_wav]) as mock_extract:
            with patch(
                "photowalk.offset_detector._load_audio",
                side_effect=[
                    (original, 16000),
                    (trimmed, 16000),
                ],
            ) as mock_load:
                result = detect_trim_offset(Path("orig.mp4"), Path("trim.mp4"))

        assert abs(result - 0.5) < 0.01
        assert mock_extract.call_count == 2
        mock_load.assert_called()

    def test_cleans_up_temp_files(self, tmp_path):
        rng = np.random.default_rng(789)
        orig_wav = tmp_path / "orig.wav"
        trim_wav = tmp_path / "trim.wav"
        orig_wav.write_text("dummy")
        trim_wav.write_text("dummy")

        original = rng.standard_normal(32000).astype(np.float32)
        start_sample = int(0.5 * 16000)
        trimmed = original[start_sample : start_sample + 16000]

        with patch("photowalk.offset_detector.extract_audio", side_effect=[orig_wav, trim_wav]):
            with patch(
                "photowalk.offset_detector._load_audio",
                side_effect=[
                    (original, 16000),
                    (trimmed, 16000),
                ],
            ):
                detect_trim_offset(Path("orig.mp4"), Path("trim.mp4"))

        assert not orig_wav.exists()
        assert not trim_wav.exists()

    def test_sample_rate_mismatch_raises(self, tmp_path):
        orig_wav = tmp_path / "orig.wav"
        trim_wav = tmp_path / "trim.wav"
        orig_wav.write_text("dummy")
        trim_wav.write_text("dummy")

        with patch("photowalk.offset_detector.extract_audio", side_effect=[orig_wav, trim_wav]):
            with patch(
                "photowalk.offset_detector._load_audio",
                side_effect=[
                    (np.array([1.0, 2.0], dtype=np.float32), 16000),
                    (np.array([1.0, 2.0], dtype=np.float32), 22050),
                ],
            ):
                with pytest.raises(OffsetDetectionError, match="Sample rate mismatch"):
                    detect_trim_offset(Path("orig.mp4"), Path("trim.mp4"))

        assert not orig_wav.exists()
        assert not trim_wav.exists()
