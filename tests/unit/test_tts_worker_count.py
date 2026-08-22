from __future__ import annotations

from unittest.mock import patch

from video_translator import container


def test_explicit_value_is_respected():
    assert container._resolve_tts_worker_count(3) == 3


def test_auto_detect_caps_at_max_even_with_many_cores():
    with patch.object(container.os, "cpu_count", return_value=64):
        assert container._resolve_tts_worker_count(0) == container._AUTO_MAX_TTS_WORKERS


def test_auto_detect_uses_full_core_count_below_the_cap():
    """Validado en un M4 Max: mas workers de los que sugeriria 'mitad de los
    nucleos' siguio mejorando el tiempo de sintesis (ver comentario en
    container.py), asi que el auto-detect ya no divide cpu_count entre 2."""
    with patch.object(container.os, "cpu_count", return_value=8):
        assert container._resolve_tts_worker_count(0) == 8


def test_auto_detect_never_returns_zero_workers():
    with patch.object(container.os, "cpu_count", return_value=None):
        assert container._resolve_tts_worker_count(0) >= 1
