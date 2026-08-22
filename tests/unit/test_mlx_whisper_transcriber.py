from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from video_translator.domain.exceptions import TranscriptionError
from video_translator.infrastructure.transcription.mlx_whisper_transcriber import (
    MlxWhisperTranscriber,
)


def _install_fake_mlx_whisper(monkeypatch, result=None, exc=None):
    fake = types.ModuleType("mlx_whisper")

    def fake_transcribe(audio, path_or_hf_repo=None, language=None, **kwargs):
        fake.calls.append(
            {"audio": audio, "path_or_hf_repo": path_or_hf_repo, "language": language}
        )
        if exc is not None:
            raise exc
        return result

    fake.calls = []
    fake.transcribe = fake_transcribe
    monkeypatch.setitem(sys.modules, "mlx_whisper", fake)
    return fake


def test_transcribe_maps_segments_to_transcript_segments(monkeypatch, tmp_path: Path):
    fake_result = {
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 2.0, "text": " Hello there. "},
            {"start": 2.0, "end": 5.0, "text": "This is a test."},
        ],
    }
    fake = _install_fake_mlx_whisper(monkeypatch, result=fake_result)

    transcriber = MlxWhisperTranscriber(model_repo="mlx-community/whisper-large-v3-mlx")
    segments = list(transcriber.transcribe(tmp_path / "audio.wav", language_hint="en"))

    assert [s.text for s in segments] == ["Hello there.", "This is a test."]
    assert [s.id for s in segments] == [0, 1]
    assert segments[0].start == 0.0 and segments[0].end == 2.0
    assert all(s.language == "en" for s in segments)
    assert fake.calls == [
        {
            "audio": str(tmp_path / "audio.wav"),
            "path_or_hf_repo": "mlx-community/whisper-large-v3-mlx",
            "language": "en",
        }
    ]


def test_transcribe_skips_empty_segments(monkeypatch, tmp_path: Path):
    fake_result = {
        "language": "en",
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "   "},
            {"start": 1.0, "end": 2.0, "text": "Not empty."},
        ],
    }
    _install_fake_mlx_whisper(monkeypatch, result=fake_result)

    transcriber = MlxWhisperTranscriber()
    segments = list(transcriber.transcribe(tmp_path / "audio.wav"))

    assert [s.text for s in segments] == ["Not empty."]


def test_transcribe_wraps_engine_failures(monkeypatch, tmp_path: Path):
    _install_fake_mlx_whisper(monkeypatch, exc=RuntimeError("boom"))

    transcriber = MlxWhisperTranscriber()
    with pytest.raises(TranscriptionError):
        list(transcriber.transcribe(tmp_path / "audio.wav"))


def test_transcribe_raises_clear_error_when_not_installed(monkeypatch, tmp_path: Path):
    monkeypatch.setitem(sys.modules, "mlx_whisper", None)  # simula ImportError

    transcriber = MlxWhisperTranscriber()
    with pytest.raises(TranscriptionError, match="mlx-whisper no esta instalado"):
        list(transcriber.transcribe(tmp_path / "audio.wav"))
