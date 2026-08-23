from __future__ import annotations

import platform
from types import SimpleNamespace
from unittest.mock import patch

from video_translator import container


def _make_settings(index_tts2_device=None, tts_backend="index_tts2"):
    return SimpleNamespace(
        tts_backend=tts_backend,
        index_tts2_device=index_tts2_device,
        index_tts2_model_dir="m",
        index_tts2_cfg_path="c",
        index_tts2_use_bf16=True,
        index_tts2_use_torch_compile=False,
        index_tts2_num_beams=3,
        index_tts2_gpt_batch_size=4,
        ffmpeg_binary="ffmpeg",
        tts_model_name="x",
        tts_device="cpu",
    )


def test_forces_cpu_on_macos_with_multiple_workers_and_no_explicit_device():
    settings = _make_settings()
    with patch.object(platform, "system", return_value="Darwin"):
        factory = container._synthesizer_factory(settings, num_workers=4)
    assert factory.keywords["device"] == "cpu"


def test_does_not_force_cpu_on_macos_with_a_single_worker():
    """Un solo proceso usando Metal (MPS) es el uso soportado oficialmente;
    solo hace falta forzar CPU cuando hay varios procesos concurrentes."""
    settings = _make_settings()
    with patch.object(platform, "system", return_value="Darwin"):
        factory = container._synthesizer_factory(settings, num_workers=1)
    assert factory.keywords["device"] is None


def test_respects_explicit_device_override():
    """Si el usuario fija INDEX_TTS2_DEVICE explicitamente, se respeta su
    eleccion (incluso si acepta el riesgo de usar mps con varios workers)."""
    settings = _make_settings(index_tts2_device="mps")
    with patch.object(platform, "system", return_value="Darwin"):
        factory = container._synthesizer_factory(settings, num_workers=4)
    assert factory.keywords["device"] == "mps"


def test_does_not_force_cpu_on_non_macos_platforms():
    """El problema (varios procesos + Metal) es especifico de macOS; en
    Linux/Windows con CUDA no aplica esta proteccion."""
    settings = _make_settings()
    with patch.object(platform, "system", return_value="Linux"):
        factory = container._synthesizer_factory(settings, num_workers=4)
    assert factory.keywords["device"] is None
