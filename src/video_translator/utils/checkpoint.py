"""Sistema de checkpointing para que el pipeline pueda reanudarse despues de un
corte de energia, crash o Ctrl-C.

Cada etapa del pipeline que produce datos intermedios volatiles (en memoria)
se "marca" como completada guardando su salida serializada en un archivo
JSON (checkpoint.json) dentro del workdir. La primera vez que una etapa
termina, sus datos se persisten; cuando el pipeline se relanza con --resume,
se cargan los datos del checkpoint y las etapas ya completadas se saltan,
evitando refabricar horas de transcripcion, diarizacion o TTS.

Las etapas con artefactos puramente basados en archivos (extraccion de audio,
subtitulos SRT, archivos WAV de TTS individuales, video final) se verifican
comprobando si el archivo existe y no esta vacio, sin necesidad de cargarlo al
checkpoint — lo que mantiene el archivo de checkpoint pequeno.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from video_translator.domain.models import (
        DiarizationSegment,
        SpeakerProfile,
        TranscriptSegment,
        TranslatedSegment,
    )

# Identificadores de etapas, en orden de ejecucion del pipeline.
STAGE_AUDIO_EXTRACTED = "audio_extracted"
STAGE_TRANSCRIBED = "transcribed"
STAGE_SPEAKERS_BUILT = "speakers_built"
STAGE_TRANSLATED = "translated"
STAGE_SUBTITLES_WRITTEN = "subtitles_written"
STAGE_TTS_SYNTHESIZED = "tts_synthesized"
STAGE_FINALIZED = "finalized"

PIPELINE_STAGES: list[str] = [
    STAGE_AUDIO_EXTRACTED,
    STAGE_TRANSCRIBED,
    STAGE_SPEAKERS_BUILT,
    STAGE_TRANSLATED,
    STAGE_SUBTITLES_WRITTEN,
    STAGE_TTS_SYNTHESIZED,
    STAGE_FINALIZED,
]

# Etapas condicionales: solo son relevantes bajo ciertas condiciones.
STAGE_REQUIRES_DIARIZE = {STAGE_SPEAKERS_BUILT}
STAGE_REQUIRES_DUBBING = {STAGE_TTS_SYNTHESIZED, STAGE_FINALIZED}


@dataclass(slots=True)
class Checkpoint:
    """Estado resumable del pipeline en un momento dado.

    Los segmentos y perfiles se guardan como listas de dicts para poder
    round-trip a traves de JSON sin depender de la definicion exacta de
    los dataclasses de dominio.
    """

    input_video: str
    input_size: int
    input_mtime: float
    source_lang_hint: str | None
    diarize: bool
    output_mode: str
    completed_stages: list[str] = field(default_factory=list)
    transcript_segments: list[dict] = field(default_factory=list)
    diarization_segments: list[dict] | None = None
    speaker_profiles: list[dict] | None = None
    translated_segments: list[dict] | None = None
    tts_job_count: int | None = None


class CheckpointStore:
    """Gestiona la persistencia y carga del checkpoint en disco."""

    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir
        self._path = workdir / "checkpoint.json"

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def load(self) -> Checkpoint | None:
        if not self._path.exists():
            return None
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        return Checkpoint(**raw)

    def save(self, checkpoint: Checkpoint) -> None:
        self._workdir.mkdir(parents=True, exist_ok=True)
        data = asdict(checkpoint)
        fd, tmp_path = tempfile.mkstemp(dir=self._workdir, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._path)
        except BaseException:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def clear(self) -> None:
        if self._path.exists():
            self._path.unlink()


def restore_transcript_segments(checkpoint: Checkpoint) -> list[TranscriptSegment]:
    from video_translator.domain.models import TranscriptSegment
    return [TranscriptSegment(**d) for d in checkpoint.transcript_segments]


def restore_diarization_segments(checkpoint: Checkpoint) -> list[DiarizationSegment] | None:
    from video_translator.domain.models import DiarizationSegment
    if checkpoint.diarization_segments is None:
        return None
    return [DiarizationSegment(**d) for d in checkpoint.diarization_segments]


def restore_speaker_profiles(checkpoint: Checkpoint) -> list[SpeakerProfile]:
    from video_translator.domain.models import SpeakerProfile
    if checkpoint.speaker_profiles is None:
        return []
    return [
        SpeakerProfile(
            speaker_id=p["speaker_id"],
            gender=p.get("gender"),
            reference_wav=Path(p["reference_wav"]) if p.get("reference_wav") else None,
        )
        for p in checkpoint.speaker_profiles
    ]


def restore_translated_segments(checkpoint: Checkpoint) -> list[TranslatedSegment] | None:
    from video_translator.domain.models import TranslatedSegment
    if checkpoint.translated_segments is None:
        return None
    return [TranslatedSegment(**d) for d in checkpoint.translated_segments]
