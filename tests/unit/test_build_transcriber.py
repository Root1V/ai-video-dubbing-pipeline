from __future__ import annotations

import pytest

from video_translator import container
from video_translator.domain.exceptions import ConfigurationError


def _settings(**overrides):
    from video_translator.config import Settings

    # _env_file=None: ignora el .env real del desarrollador (que puede tener
    # WHISPER_BACKEND=mlx configurado localmente) para que el test verifique
    # los defaults del propio modelo Settings, no el entorno de quien corre
    # la suite.
    return Settings(_env_file=None, **overrides)


def test_defaults_to_faster_whisper():
    from video_translator.infrastructure.transcription.faster_whisper_transcriber import (
        FasterWhisperTranscriber,
    )

    transcriber = container._build_transcriber(_settings(), enable_diarization=False)
    assert isinstance(transcriber, FasterWhisperTranscriber)


def test_mlx_backend_builds_mlx_transcriber():
    from video_translator.infrastructure.transcription.mlx_whisper_transcriber import (
        MlxWhisperTranscriber,
    )

    settings = _settings(whisper_backend="mlx", mlx_whisper_model="mlx-community/whisper-large-v3-mlx")
    transcriber = container._build_transcriber(settings, enable_diarization=False)
    assert isinstance(transcriber, MlxWhisperTranscriber)
    assert transcriber._model_repo == "mlx-community/whisper-large-v3-mlx"


def test_unknown_backend_raises_configuration_error():
    settings = _settings(whisper_backend="not_a_real_backend")
    with pytest.raises(ConfigurationError):
        container._build_transcriber(settings, enable_diarization=False)
