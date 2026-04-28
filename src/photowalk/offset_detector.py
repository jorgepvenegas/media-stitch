"""Detect temporal offset between original and trimmed videos via audio cross-correlation."""

import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy import signal


class OffsetDetectionError(Exception):
    """Raised when offset detection fails for any reason."""


def extract_audio(path: Path) -> Path:
    """Extract the first audio track to a temporary 16kHz mono WAV file via ffmpeg.

    Returns the path to the temporary WAV. The caller is responsible for cleanup.
    Raises OffsetDetectionError on ffmpeg failure.
    """
    temp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp.close()
    temp_path = Path(temp.name)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(path),
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        str(temp_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temp_path.unlink(missing_ok=True)
        raise OffsetDetectionError(
            f"Failed to extract audio from {path}: {result.stderr}"
        )

    return temp_path


def _load_audio(path: Path) -> tuple[np.ndarray, int]:
    """Load a WAV file as a mono float32 numpy array and return (array, sample_rate)."""
    with wave.open(str(path), "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        data = wf.readframes(nframes)

        if sampwidth == 2:
            arr = np.frombuffer(data, dtype=np.int16)
        else:
            raise OffsetDetectionError(f"Unsupported sample width: {sampwidth}")

        if nchannels > 1:
            arr = arr.reshape(-1, nchannels).mean(axis=1)

        return arr.astype(np.float32), framerate


def find_audio_offset(original: np.ndarray, trimmed: np.ndarray, sample_rate: int) -> float:
    """Find the temporal offset (in seconds) of trimmed audio within original audio via cross-correlation.

    Raises OffsetDetectionError if the correlation confidence is below 0.5 or if
    trimmed is longer than original.
    """
    if len(trimmed) > len(original):
        raise OffsetDetectionError("Trimmed audio is longer than original")

    original_norm = (original - original.mean()) / (original.std() + 1e-10)
    trimmed_norm = (trimmed - trimmed.mean()) / (trimmed.std() + 1e-10)

    correlation = signal.correlate(original_norm, trimmed_norm, mode="valid", method="fft")
    peak_idx = int(np.argmax(correlation))
    peak_val = float(correlation[peak_idx])

    confidence = peak_val / len(trimmed_norm)
    if confidence < 0.5:
        raise OffsetDetectionError(
            f"Could not reliably detect trim point (confidence: {confidence:.2f}). "
            "Videos may be too different."
        )

    return float(peak_idx / sample_rate)


def detect_trim_offset(original_path: Path, trimmed_path: Path) -> float:
    """Detect the temporal offset (in seconds) of a trimmed video relative to its original.

    Extracts audio from both videos, loads the WAV data, and runs cross-correlation.
    Cleans up temporary files regardless of success or failure.
    Raises OffsetDetectionError on any failure.
    """
    original_wav: Path | None = None
    trimmed_wav: Path | None = None

    try:
        original_wav = extract_audio(original_path)
        trimmed_wav = extract_audio(trimmed_path)

        original_audio, original_sr = _load_audio(original_wav)
        trimmed_audio, trimmed_sr = _load_audio(trimmed_wav)

        if original_sr != trimmed_sr:
            raise OffsetDetectionError(
                f"Sample rate mismatch: {original_sr} vs {trimmed_sr}"
            )

        offset = find_audio_offset(original_audio, trimmed_audio, original_sr)

        original_duration = len(original_audio) / original_sr
        if offset > original_duration:
            raise OffsetDetectionError(
                f"Detected offset ({offset:.2f}s) exceeds original duration"
            )

        return offset
    finally:
        if original_wav is not None:
            original_wav.unlink(missing_ok=True)
        if trimmed_wav is not None:
            trimmed_wav.unlink(missing_ok=True)
