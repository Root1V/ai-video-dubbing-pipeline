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
    timings: dict = field(default_factory=dict)


@dataclass(slots=True)
class TranscribeMediaRequest:
    """Solicitud de transcripcion standalone (sin traduccion ni doblaje):
    entrada principal de ``TranscribeMediaUseCase``."""

    input_media: Path
    output_dir: Path
    source_lang_hint: str | None = None
    include_summary: bool = False


@dataclass(slots=True)
class TranscribeMediaResult:
    """Resultado de una transcripcion standalone."""

    transcript_srt_path: Path
    transcript_text_path: Path
    segments: list[TranscriptSegment]
    duration_seconds: float
    timings: dict = field(default_factory=dict)
    summary_text: str | None = None


@dataclass(slots=True)
class SynthesizeTextRequest:
    """Solicitud de sintesis de voz standalone (texto -> audio), entrada
    principal de ``SynthesizeTextUseCase``."""

    text: str
    output_dir: Path
    language: str = "es"
    speaker_reference_wav: Path | None = None  # None = usa la voz por defecto


@dataclass(slots=True)
class SynthesizeTextResult:
    """Resultado de una sintesis de voz standalone."""

    audio_path: Path
    duration_seconds: float
    timings: dict = field(default_factory=dict)


@dataclass(slots=True)
class TextOverlay:
    """Un texto libre superpuesto al micro-video (ver RM-28), posicionado a
    mano por el usuario en un editor drag & drop. `x`/`y` son fracciones
    0-1 del ancho/alto del video -- el CENTRO del texto, no la esquina
    (coincide con "donde soltaste el texto al arrastrarlo")."""

    text: str
    x: float
    y: float
    bold: bool = False
    font_family: str = "Arial"
    font_size: int = 48
    color: str = "#FFFFFF"  # hex "#RRGGBB"
    fade: bool = False  # aparece/desaparece gradual en vez de un corte seco


@dataclass(slots=True)
class GenerateMicroVideoRequest:
    """Solicitud de generacion de un micro-video (imagen + texto -> video
    vertical narrado con captions), entrada principal de
    ``GenerateMicroVideoUseCase``."""

    image_path: Path
    text: str
    output_dir: Path
    language: str = "es"
    speaker_reference_wav: Path | None = None  # None = usa la voz por defecto
    # None = el video dura lo que tarda la narracion (comportamiento previo).
    # Si se fija: narracion mas larga se acelera (atempo) para encajar;
    # narracion mas corta deja el Ken Burns corriendo el tiempo restante.
    target_duration_seconds: float | None = None
    caption_bg_color: str = "#000000"  # hex "#RRGGBB", ver caption_highlight_style
    # "background" = caja de fondo opaca de ese color detras del texto blanco
    # (comportamiento previo). "text_color" = el texto queda de ese color en
    # vez de blanco, sin caja (solo contorno para legibilidad).
    caption_highlight_style: str = "background"
    # None = sin musica de fondo (comportamiento previo). Si se fija, se
    # mezcla en volumen bajo debajo de la narracion (nunca debe taparla) y
    # se ajusta (loop/recorte) a la duracion final del video.
    background_music_path: Path | None = None
    # Rango [start, end) DENTRO de background_music_path a usar como fuente
    # del loop (ver RM-28) -- None en end = hasta el final de la pista.
    # Ignorado si background_music_path es None.
    background_music_start: float = 0.0
    background_music_end: float | None = None
    # Volumen lineal (no dB) de la musica de fondo al mezclarla -- mismo
    # default que el que ya tenia mix_background_music. Ignorado si
    # background_music_path es None.
    background_music_volume: float = 0.12
    # Volumen lineal (no dB) de la narracion, 1.0 = sin cambios. Se aplica
    # SIEMPRE (haya o no musica de fondo) -- ver GenerateMicroVideoUseCase.
    narration_volume: float = 1.0
    # Textos superpuestos posicionables (ver RM-28) -- lista vacia = sin
    # overlays, comportamiento previo (solo captions de la narracion).
    text_overlays: list[TextOverlay] = field(default_factory=list)
    # Posicion de los captions de la narracion (fraccion 0-1 del ancho/alto
    # del video, CENTRO del caption -- mismo criterio que TextOverlay.x/y,
    # arrastrable en el editor igual que un overlay de texto).
    caption_x: float = 0.5
    caption_y: float = 0.85


@dataclass(slots=True)
class GenerateMicroVideoResult:
    """Resultado de una generacion de micro-video."""

    output_video: Path
    duration_seconds: float
    timings: dict = field(default_factory=dict)
