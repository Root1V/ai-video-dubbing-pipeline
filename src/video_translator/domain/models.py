"""Modelos de dominio: entidades y value objects puros, sin dependencias de infraestructura."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class OutputMode(str, Enum):
    """Modo de salida del video traducido."""

    SUBTITLES_ONLY = "subtitles_only"       # Solo genera .srt (EN y ES)
    BURN_SUBTITLES = "burn_subtitles"       # Incrusta subtitulos ES en el video
    SOFT_SUBTITLES = "soft_subtitles"       # Adjunta subtitulos ES como pista seleccionable
    DUBBED = "dubbed"                       # Reemplaza el audio por voz sintetizada en ES


@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    """Un segmento de audio transcrito en el idioma original."""

    id: int
    start: float          # segundos
    end: float             # segundos
    text: str
    language: str = "en"
    speaker_id: str | None = None  # p.ej. "SPEAKER_00", asignado por diarizacion

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True, slots=True)
class TranslatedSegment:
    """Un segmento ya traducido, conserva el timing original para sincronizar subtitulos/audio."""

    id: int
    start: float
    end: float
    source_text: str
    translated_text: str
    speaker_id: str | None = None

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(frozen=True, slots=True)
class DiarizationSegment:
    """Un turno de habla detectado por el pipeline de diarizacion (quien habla y cuando)."""

    start: float
    end: float
    speaker_label: str

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass(slots=True)
class SpeakerProfile:
    """Perfil de un hablante detectado: su etiqueta, genero estimado y clip de referencia
    (usado para clonar su timbre de voz en el doblaje)."""

    speaker_id: str
    gender: str | None = None  # "male" | "female" | "unknown"
    reference_wav: Path | None = None


@dataclass(slots=True)
class TranslationContext:
    """Contexto proporcionado por el usuario para guiar y mejorar la calidad de la traduccion.

    Este es el mecanismo central que permite mejorar la salida del LLM: un prompt en
    lenguaje natural describiendo dominio, tono, audiencia, y un glosario opcional de
    terminos que deben traducirse (o no) de forma consistente.
    """

    prompt: str = ""
    glossary: dict[str, str] = field(default_factory=dict)
    source_lang: str = "en"
    target_lang: str = "es"
    tone: str | None = None  # p.ej. "formal", "informal", "tecnico"
    speaker_genders: dict[str, str] = field(default_factory=dict)  # speaker_id -> "male"/"female"/"unknown"

    def is_empty(self) -> bool:
        return not self.prompt and not self.glossary


@dataclass(slots=True)
class TranslateVideoRequest:
    """Solicitud de traduccion de un video, entrada principal del caso de uso."""

    input_video: Path
    output_dir: Path
    context: TranslationContext
    output_mode: OutputMode = OutputMode.SOFT_SUBTITLES
    keep_original_audio_track: bool = True
    speaker_reference_wav: Path | None = None  # voz unica de referencia (fallback sin diarizacion)
    source_lang_hint: str | None = "en"
    diarize: bool = False               # activa deteccion de multiples hablantes
    min_speakers: int | None = None
    max_speakers: int | None = None


@dataclass(slots=True)
class TranslateVideoResult:
    """Resultado del pipeline completo."""

    output_video: Path | None
    subtitles_source_path: Path
    subtitles_target_path: Path
    segments: list[TranslatedSegment]
    duration_seconds: float
    speakers: list[SpeakerProfile] = field(default_factory=list)
