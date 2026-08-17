"""Alinea la transcripcion (Whisper) con la diarizacion (pyannote) y arma, por cada
hablante detectado, un clip de audio de referencia apto para clonacion de voz.

Whisper y el pipeline de diarizacion producen segmentaciones independientes con
limites de tiempo distintos (Whisper agrupa por frases/pausas; la diarizacion
por turnos de habla). Para asignar un hablante a cada linea de subtitulo/doblaje
se usa el criterio de maximo solapamiento temporal.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from video_translator.domain.models import DiarizationSegment, TranscriptSegment

DEFAULT_MIN_REFERENCE_SECONDS = 6.0
DEFAULT_MAX_REFERENCE_SECONDS = 15.0


def assign_speakers(
    transcript_segments: list[TranscriptSegment], diarization_segments: list[DiarizationSegment]
) -> list[TranscriptSegment]:
    """Devuelve una copia de ``transcript_segments`` con ``speaker_id`` completado,
    asignando a cada segmento el hablante cuyo turno se solapa mas en el tiempo.
    """
    if not diarization_segments:
        return transcript_segments

    result: list[TranscriptSegment] = []
    for seg in transcript_segments:
        best_label: str | None = None
        best_overlap = 0.0
        for turn in diarization_segments:
            overlap = _overlap(seg.start, seg.end, turn.start, turn.end)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = turn.speaker_label
        result.append(dataclasses.replace(seg, speaker_id=best_label))
    return result


def _overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def select_reference_windows(
    diarization_segments: list[DiarizationSegment],
    min_seconds: float = DEFAULT_MIN_REFERENCE_SECONDS,
    max_seconds: float = DEFAULT_MAX_REFERENCE_SECONDS,
) -> dict[str, tuple[float, float]]:
    """Por cada hablante, elige la ventana de tiempo mas apta para usar como
    muestra de voz de referencia: el turno continuo mas largo, recortado a
    ``max_seconds`` si es necesario. Descarta hablantes cuyo turno mas largo no
    alcance ``min_seconds`` (probable ruido o intervencion muy breve).
    """
    longest_by_speaker: dict[str, DiarizationSegment] = {}
    for turn in diarization_segments:
        current = longest_by_speaker.get(turn.speaker_label)
        if current is None or turn.duration > current.duration:
            longest_by_speaker[turn.speaker_label] = turn

    windows: dict[str, tuple[float, float]] = {}
    for label, turn in longest_by_speaker.items():
        if turn.duration < min_seconds:
            continue
        end = turn.start + min(turn.duration, max_seconds)
        windows[label] = (turn.start, end)
    return windows


def unique_speaker_labels(diarization_segments: list[DiarizationSegment]) -> list[str]:
    seen: dict[str, None] = {}
    for turn in diarization_segments:
        seen.setdefault(turn.speaker_label, None)
    return list(seen.keys())
