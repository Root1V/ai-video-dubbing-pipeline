from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from video_translator.infrastructure.synthesis.audio_mixing import (
    _build_atempo_chain,
    fit_to_duration,
    wav_duration_seconds,
)


def _write_silent_wav(path: Path, duration_seconds: float, sample_rate: int = 16000) -> Path:
    num_frames = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(b"\x00\x00" * num_frames)
    return path


def _approx_product(stages: list[float]) -> float:
    result = 1.0
    for s in stages:
        result *= s
    return result


# --- _build_atempo_chain: descomposicion en etapas validas ---------------


def test_chain_single_stage_when_factor_within_range():
    assert _build_atempo_chain(1.3) == [1.3]
    assert _build_atempo_chain(0.8) == [0.8]


def test_chain_splits_factor_above_two():
    chain = _build_atempo_chain(2.5)
    assert all(0.5 <= s <= 2.0 for s in chain)
    assert len(chain) > 1
    assert _approx_product(chain) == _approx_eq(2.5)


def test_chain_splits_large_factor_into_multiple_stages():
    chain = _build_atempo_chain(5.0)
    assert all(0.5 <= s <= 2.0 for s in chain)
    assert _approx_product(chain) == _approx_eq(5.0)


def test_chain_splits_factor_below_half():
    chain = _build_atempo_chain(0.2)
    assert all(0.5 <= s <= 2.0 for s in chain)
    assert _approx_product(chain) == _approx_eq(0.2)


def _approx_eq(value, rel=1e-6):
    class _Approx:
        def __eq__(self, other):
            return abs(other - value) <= abs(value) * rel + 1e-9

    return _Approx()


# --- fit_to_duration: factor calculado de forma independiente por llamada -


def _patch_run_capture(monkeypatch) -> dict:
    captured: dict = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        # Simula que ffmpeg "aplico" el cambio: como el test no necesita el
        # resultado real, simplemente no falla (CalledProcessError no se lanza).
        class Result:
            pass

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    return captured


def test_fit_to_duration_skips_processing_within_tolerance(tmp_path: Path, monkeypatch):
    captured = _patch_run_capture(monkeypatch)
    clip = _write_silent_wav(tmp_path / "a.wav", duration_seconds=2.0)

    result = fit_to_duration(clip, target_seconds=2.01, ffmpeg_binary="ffmpeg")

    assert result is True
    assert "cmd" not in captured  # no se llamo a ffmpeg, la diferencia es despreciable


def test_fit_to_duration_computes_independent_factor_per_call(tmp_path: Path, monkeypatch):
    """Dos llamadas con distinta duracion actual/objetivo deben producir
    factores de compresion DISTINTOS — nunca un valor compartido/fijo."""
    captured_filters = []

    def fake_run(cmd, capture_output, text, check):
        idx = cmd.index("-filter:a") + 1
        captured_filters.append(cmd[idx])

        class Result:
            pass

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    clip_a = _write_silent_wav(tmp_path / "a.wav", duration_seconds=3.0)  # necesita comprimir x1.5
    clip_b = _write_silent_wav(tmp_path / "b.wav", duration_seconds=3.0)  # necesita comprimir x3.0

    # tmp_path.replace requiere que exista el archivo de salida; como
    # simulamos ffmpeg, creamos el ".tmp.wav" para que el rename no falle.
    for clip in (clip_a, clip_b):
        clip.with_suffix(".tmp.wav").touch()

    fit_to_duration(clip_a, target_seconds=2.0, ffmpeg_binary="ffmpeg")  # factor esperado: 1.5
    fit_to_duration(clip_b, target_seconds=1.0, ffmpeg_binary="ffmpeg")  # factor esperado: 3.0

    assert len(captured_filters) == 2
    assert captured_filters[0] != captured_filters[1]
    assert "atempo=1.5000" in captured_filters[0]
    # 3.0 no cabe en una sola instancia de atempo (>2.0): debe venir encadenado.
    assert "atempo=2.0000,atempo=1.5000" in captured_filters[1]


def test_fit_to_duration_never_caps_compression(tmp_path: Path, monkeypatch):
    """A diferencia de una version anterior que topaba la compresion a 1.6x,
    ahora un desfase grande debe comprimirse por completo (encadenando),
    nunca dejarse a medias para que algo mas adelante tenga que recortar."""
    captured_filters = []

    def fake_run(cmd, capture_output, text, check):
        idx = cmd.index("-filter:a") + 1
        captured_filters.append(cmd[idx])

        class Result:
            pass

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    clip = _write_silent_wav(tmp_path / "a.wav", duration_seconds=10.0)
    clip.with_suffix(".tmp.wav").touch()

    # Un clip 5x mas largo que su hueco: con el limite viejo (1.6x) esto
    # habria quedado ~3.1x demasiado largo. Ahora debe comprimirse completo.
    result = fit_to_duration(clip, target_seconds=2.0, ffmpeg_binary="ffmpeg")

    assert result is True
    filter_str = captured_filters[0]
    stages = [float(s.split("=")[1]) for s in filter_str.split(",")]
    assert all(0.5 <= s <= 2.0 for s in stages)
    assert _approx_product(stages) == _approx_eq(5.0)


def test_fit_to_duration_returns_false_and_keeps_file_on_ffmpeg_failure(tmp_path: Path, monkeypatch):
    def fake_run(cmd, capture_output, text, check):
        raise subprocess.CalledProcessError(1, cmd, stderr="boom")

    monkeypatch.setattr(subprocess, "run", fake_run)

    clip = _write_silent_wav(tmp_path / "a.wav", duration_seconds=5.0)
    original_duration = wav_duration_seconds(clip)

    result = fit_to_duration(clip, target_seconds=2.0, ffmpeg_binary="ffmpeg")

    assert result is False
    # El archivo original no debe haberse tocado (no se aplico tmp_path.replace).
    assert wav_duration_seconds(clip) == original_duration


def test_fit_to_duration_slowdown_has_a_floor(tmp_path: Path, monkeypatch):
    """Si el clip quedo mucho mas corto que su hueco, no se lo alarga sin
    limite (eso no arriesga solapamiento, asi que no hace falta forzarlo)."""
    captured_filters = []

    def fake_run(cmd, capture_output, text, check):
        idx = cmd.index("-filter:a") + 1
        captured_filters.append(cmd[idx])

        class Result:
            pass

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)

    clip = _write_silent_wav(tmp_path / "a.wav", duration_seconds=1.0)
    clip.with_suffix(".tmp.wav").touch()

    # target=4.0 -> factor natural = 0.25, muy por debajo del piso de 0.75.
    fit_to_duration(clip, target_seconds=4.0, ffmpeg_binary="ffmpeg")

    filter_str = captured_filters[0]
    stages = [float(s.split("=")[1]) for s in filter_str.split(",")]
    assert _approx_product(stages) == _approx_eq(0.75)
