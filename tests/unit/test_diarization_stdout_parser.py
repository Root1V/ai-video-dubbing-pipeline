"""Tests del parsing tolerante de la salida del worker de diarizacion.

Caso real que lo motivo (clip de 13 min, corrida del 2026-08-22): pyannote
imprimio 'WARNING: Value of auxiliary function has decreased!' en stdout
ANTES del JSON y el json.loads() directo del texto completo rechazaba una
diarizacion de ~45 minutos de CPU. El parser debe recuperar el JSON aunque
haya ruido previo.
"""

from __future__ import annotations

import pytest

from video_translator.domain.exceptions import DiarizationError
from video_translator.infrastructure.diarization.subprocess_diarizer import (
    SubprocessDiarizer,
)

CLEAN = '{"segments": [{"start": 0.0, "end": 1.0, "speaker_label": "SPEAKER_00"}], "timings": {"inference_seconds": 12.5}}'

CONTAMINATED = (
    "WARNING: Value of auxiliary function has decreased!\n"
    '{"segments": [{"start": 0.03, "end": 17.44, "speaker_label": "SPEAKER_00"}], '
    '"timings": {"model_load_seconds": 9.1, "inference_seconds": 2450.3}}'
)

MULTILINE_WARNING = (
    "Some torch warning line 1\n"
    "line 2 about deprecation\n"
    '{\n'
    '  "segments": [],\n'
    '  "timings": {}\n'
    "}\n"
)


def test_extracts_clean_json():
    data = SubprocessDiarizer._extract_json_output(CLEAN)
    assert data["segments"][0]["speaker_label"] == "SPEAKER_00"


def test_extracts_json_after_pyannote_warning_line():
    # El caso real que costo 45 minutos de CPU: warning antes del JSON.
    data = SubprocessDiarizer._extract_json_output(CONTAMINATED)
    assert len(data["segments"]) == 1
    assert data["timings"]["inference_seconds"] == 2450.3


def test_extracts_multiline_json_with_leading_noise():
    data = SubprocessDiarizer._extract_json_output(MULTILINE_WARNING)
    assert data == {"segments": [], "timings": {}}


def test_raises_when_no_json_present():
    with pytest.raises(DiarizationError, match="no se encontro JSON"):
        SubprocessDiarizer._extract_json_output("solo ruido\nsin json\n")


def test_raises_on_truncated_json():
    truncated = 'WARNING: x\n{"segments": [{"start": 0.0, '
    with pytest.raises(DiarizationError, match="no se encontro JSON"):
        SubprocessDiarizer._extract_json_output(truncated)
