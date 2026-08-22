"""Agrupa segmentos de transcripcion traducidos en unidades mas grandes para
sintesis de voz, reduciendo drasticamente el numero de llamadas al motor de
TTS en videos largos.

Por que hace falta: un video de una hora puede producir mas de mil segmentos
de transcripcion (Whisper corta por pausas naturales, ~3s en promedio). Cada
llamada de sintesis tiene un costo fijo (arranque de la generacion
autoregresiva) ademas del costo proporcional al texto; con miles de llamadas
ese costo fijo domina el tiempo total. Fusionar segmentos consecutivos del
MISMO hablante, con poco silencio entre ellos, en una sola llamada de TTS mas
larga reduce el numero de llamadas sin perder la asignacion de hablante ni la
sincronizacion (el grupo conserva el timestamp de inicio del primer segmento
y se recorta al hueco real hasta el siguiente grupo, igual que un segmento
individual).

Regla de seguridad: SOLO se fusionan segmentos con ``speaker_id`` no nulo e
identico (es decir, confirmado por diarizacion). Segmentos sin hablante
identificado (``speaker_id is None``, el caso sin ``--diarize``) nunca se
fusionan entre si, porque no hay garantia de que pertenezcan a la misma
persona hablando de forma continua.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from video_translator.domain.models import TranslatedSegment

DEFAULT_MAX_GAP_SECONDS = 0.5
DEFAULT_MAX_GROUP_CHARS = 200


@dataclass(frozen=True, slots=True)
class SynthesisGroup:
    """Una o mas ``TranslatedSegment`` consecutivas del mismo hablante,
    tratadas como una sola unidad de sintesis de voz."""

    start: float
    end: float
    speaker_id: str | None
    text: str
    member_ids: tuple[int, ...] = field(default_factory=tuple)

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def group_segments_for_synthesis(
    segments: list[TranslatedSegment],
    max_gap_seconds: float = DEFAULT_MAX_GAP_SECONDS,
    max_group_chars: int = DEFAULT_MAX_GROUP_CHARS,
) -> list[SynthesisGroup]:
    if not segments:
        return []

    groups: list[SynthesisGroup] = []
    current_members: list[TranslatedSegment] = [segments[0]]

    def _flush() -> None:
        texts = " ".join(s.translated_text for s in current_members)
        groups.append(
            SynthesisGroup(
                start=current_members[0].start,
                end=current_members[-1].end,
                speaker_id=current_members[0].speaker_id,
                text=texts,
                member_ids=tuple(s.id for s in current_members),
            )
        )

    for seg in segments[1:]:
        prev = current_members[-1]
        same_speaker = prev.speaker_id is not None and prev.speaker_id == seg.speaker_id
        gap = seg.start - prev.end
        combined_len = len(" ".join(s.translated_text for s in current_members)) + 1 + len(
            seg.translated_text
        )

        if same_speaker and gap <= max_gap_seconds and combined_len <= max_group_chars:
            current_members.append(seg)
        else:
            _flush()
            current_members = [seg]

    _flush()
    return groups
