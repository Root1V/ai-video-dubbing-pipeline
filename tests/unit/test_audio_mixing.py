from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import pytest

from video_translator.domain.exceptions import SynthesisError
from video_translator.infrastructure.synthesis import audio_mixing


def _write_silent_wav(path: Path, duration_seconds: float, sample_rate: int = 16000) -> Path:
    """Genera un .wav real (silencio) de la duracion pedida, para que
    wav_duration_seconds() pueda leerlo como cualquier clip de TTS real."""
    num_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)  # 16-bit
        f.setframerate(sample_rate)
        f.writeframes(b"\x00\x00" * num_frames)
    return path


def _patch_run_capture(monkeypatch) -> dict:
    captured: dict = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd

        class Result:
            pass

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    return captured


def test_concatenate_segments_raises_on_empty_list(tmp_path: Path):
    with pytest.raises(SynthesisError):
        audio_mixing.concatenate_segments([], 10.0, tmp_path / "out.wav")


def test_no_trim_applied_when_clip_already_fits(tmp_path: Path, monkeypatch):
    """Si el audio generado ya entra en su hueco disponible, NO debe
    recortarse "por las dudas" — solo se agrega el delay y se mezcla tal cual."""
    captured = _patch_run_capture(monkeypatch)

    clip = _write_silent_wav(tmp_path / "a.wav", duration_seconds=1.5)

    audio_mixing.concatenate_segments(
        segment_audio_paths=[(0.0, clip, 2.0)],  # clip de 1.5s, hueco de 2.0s: entra sin problema
        total_duration=5.0,
        output_path=tmp_path / "out.wav",
    )

    filter_complex = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
    assert "atrim" not in filter_complex
    assert "afade" not in filter_complex
    assert "adelay=0|0" in filter_complex


def test_trim_and_fade_applied_only_when_clip_overflows(tmp_path: Path, monkeypatch):
    """Si el audio generado quedo mas largo que su hueco disponible, se
    recorta a ese limite CON un fundido de salida corto (no un corte seco)."""
    captured = _patch_run_capture(monkeypatch)

    clip_a = _write_silent_wav(tmp_path / "a.wav", duration_seconds=3.0)  # excede su hueco de 2.0s
    clip_b = _write_silent_wav(tmp_path / "b.wav", duration_seconds=2.0)  # entra bien en su hueco de 3.0s

    audio_mixing.concatenate_segments(
        segment_audio_paths=[(0.0, clip_a, 2.0), (2.0, clip_b, 3.0)],
        total_duration=5.0,
        output_path=tmp_path / "out.wav",
    )

    filter_complex = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]

    # Segmento 0 SI se recorta (excedia su hueco) y lleva fundido de salida.
    assert "atrim=start=0:end=2.000" in filter_complex
    assert "afade=t=out" in filter_complex
    # Segmento 1 NO se recorta (ya entraba bien).
    assert "atrim=start=0:end=3.000" not in filter_complex

    assert "adelay=0|0" in filter_complex
    assert "adelay=2000|2000" in filter_complex
    assert "amix=inputs=2" in filter_complex


def test_enforces_minimum_trim_floor(tmp_path: Path, monkeypatch):
    """Un hueco casi nulo no debe producir un atrim de duracion 0/negativa."""
    captured = _patch_run_capture(monkeypatch)
    clip = _write_silent_wav(tmp_path / "a.wav", duration_seconds=1.0)

    audio_mixing.concatenate_segments(
        segment_audio_paths=[(0.0, clip, 0.0)],  # hueco de 0s, clip de 1s: fuerza el recorte
        total_duration=1.0,
        output_path=tmp_path / "out.wav",
    )

    filter_complex = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
    assert "atrim=start=0:end=0.050" in filter_complex  # piso minimo aplicado
