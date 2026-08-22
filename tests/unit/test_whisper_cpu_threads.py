from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from video_translator import container


def _settings(whisper_cpu_threads: int) -> SimpleNamespace:
    return SimpleNamespace(whisper_cpu_threads=whisper_cpu_threads)


def test_respects_explicit_cpu_threads_even_with_diarization():
    settings = _settings(whisper_cpu_threads=8)
    assert container._resolve_whisper_cpu_threads(settings, enable_diarization=True) == 8


def test_auto_without_diarization_stays_auto():
    """Sin diarizacion concurrente no hay con quien competir por nucleos:
    se deja en 0 (CTranslate2 lo interpreta como "usar todos")."""
    settings = _settings(whisper_cpu_threads=0)
    assert container._resolve_whisper_cpu_threads(settings, enable_diarization=False) == 0


def test_auto_with_diarization_reserves_cores():
    """Con diarizacion corriendo en paralelo (misma maquina, CPU-bound), se
    reserva un margen de nucleos para el subprocess de pyannote en vez de
    dejar que whisper reclame la maquina entera y ambos se frenen mutuamente."""
    settings = _settings(whisper_cpu_threads=0)
    with patch.object(container.os, "cpu_count", return_value=16):
        result = container._resolve_whisper_cpu_threads(settings, enable_diarization=True)
    assert result == 16 - container._CORES_RESERVED_FOR_DIARIZATION


def test_auto_with_diarization_never_goes_below_one_core():
    settings = _settings(whisper_cpu_threads=0)
    with patch.object(container.os, "cpu_count", return_value=2):
        result = container._resolve_whisper_cpu_threads(settings, enable_diarization=True)
    assert result >= 1
