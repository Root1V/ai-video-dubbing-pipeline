"""Traduce un `Project` (fila de BD) a los objetos de entrada del pipeline real.

Replica exactamente la receta de `cli.py::translate` (carga de `Settings`,
overrides puntuales, `TranslationContext`/`TranslateVideoRequest`, logging por
corrida) para que la tarea Celery sea ese mismo camino sin la parte de
consola. No se modifica `application`/`domain`: esto es un adaptador nuevo,
igual que `cli.py` es "otro driver" del mismo caso de uso.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from video_translator.application.use_cases.generate_micro_video import GenerateMicroVideoUseCase
from video_translator.application.use_cases.synthesize_text import SynthesizeTextUseCase
from video_translator.application.use_cases.transcribe_media import TranscribeMediaUseCase
from video_translator.application.use_cases.translate_video import TranslateVideoUseCase
from video_translator.config import load_settings
from video_translator.container import (
    PUBLIC_VOICE_FEMALE_WAV,
    PUBLIC_VOICE_MALE_WAV,
    build_generate_micro_video_use_case,
    build_synthesize_text_use_case,
    build_transcribe_media_use_case,
    build_translate_video_use_case,
)
from video_translator.domain.models import (
    EmojiOverlay,
    GenerateMicroVideoRequest,
    MicroVideoImage,
    OutputMode,
    SynthesizeTextRequest,
    TextOverlay,
    TranscribeMediaRequest,
    TranslateVideoRequest,
    TranslationContext,
)
from video_translator.utils.logging_config import configure_logging
from video_translator.web.db.models import MusicTrack, Project


def _resolve_background_music_path(background_music_track: str | None, db: Session) -> Path | None:
    """Resuelve el id de `MusicTrack` guardado en `config['background_music']`
    a su archivo real -- None si no se eligio pista o si el id ya no existe
    (p.ej. fue borrada desde el panel de mantenimiento, ver RM-26)."""
    if not background_music_track:
        return None
    try:
        track_id = uuid.UUID(background_music_track)
    except ValueError:
        return None
    track = db.get(MusicTrack, track_id)
    return Path(track.file_path) if track is not None else None


def _config_float(config: dict, key: str, default: float) -> float:
    """Lee un float de `config` con fallback -- a diferencia de `value or
    default`, distingue None (ausente, usar default) de 0.0 (valor real
    valido, p.ej. un volumen silenciado)."""
    value = config.get(key)
    return float(value) if value is not None else default


def _parse_text_overlays(raw_overlays: object) -> list[TextOverlay]:
    """Convierte la lista de dicts guardada en `config['text_overlays']`
    (ver RM-28, `routers/projects.py::create_project` ya valido que cada
    item tiene 'text'/'x'/'y') en `TextOverlay`s -- las claves opcionales
    ausentes toman el default del dataclass."""
    if not isinstance(raw_overlays, list):
        return []
    overlays = []
    for item in raw_overlays:
        if not isinstance(item, dict):
            continue
        kwargs = {
            key: item[key]
            for key in (
                "text", "x", "y", "bold", "font_family", "font_size", "color", "fade",
                "text_style", "gradient_color",
            )
            if key in item
        }
        overlays.append(TextOverlay(**kwargs))
    return overlays


def _parse_emoji_overlays(raw_overlays: object) -> list[EmojiOverlay]:
    """Convierte la lista de dicts guardada en `config['emoji_overlays']`
    (ver RM-32, `routers/projects.py::create_project` ya valido que cada
    item tiene 'emoji_id'/'x'/'y') en `EmojiOverlay`s -- las claves
    opcionales ausentes toman el default del dataclass."""
    if not isinstance(raw_overlays, list):
        return []
    overlays = []
    for item in raw_overlays:
        if not isinstance(item, dict):
            continue
        kwargs = {key: item[key] for key in ("emoji_id", "x", "y", "size", "fade") if key in item}
        overlays.append(EmojiOverlay(**kwargs))
    return overlays


def _parse_image_adjustments(raw_adjustments: object, image_paths: list[Path]) -> list[MicroVideoImage]:
    """Combina `image_paths` (ya resuelto: imagen principal + adicionales,
    ver RM-29) con la lista JSON guardada en `config['image_adjustments']`
    (ver RM-30, `routers/projects.py::create_project`), por indice -- si
    falta el ajuste de un indice (longitud desalineada, o el proyecto es
    anterior a RM-30 y no tiene esta clave) usa los defaults del dataclass
    (recorte centrado, sin zoom manual, sin filtro de color -- ver RM-31)."""
    adjustments = raw_adjustments if isinstance(raw_adjustments, list) else []
    images = []
    for i, path in enumerate(image_paths):
        item = adjustments[i] if i < len(adjustments) and isinstance(adjustments[i], dict) else {}
        kwargs = {key: item[key] for key in ("offset_x", "offset_y", "zoom", "filter_preset") if key in item}
        images.append(MicroVideoImage(path=path, **kwargs))
    return images


def build_use_case_and_request(
    project: Project, resume: bool = False
) -> tuple[TranslateVideoUseCase, TranslateVideoRequest]:
    settings = load_settings()

    config = project.config or {}
    tts_workers = config.get("tts_workers")
    if tts_workers is not None:
        settings.tts_parallel_workers = int(tts_workers)
    group_segments = config.get("group_segments")
    if group_segments is not None:
        settings.tts_group_segments = bool(group_segments)

    output_dir = Path(project.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "logs" / f"run_{datetime.now().astimezone():%Y%m%d_%H%M%S}.log"
    configure_logging(level=settings.log_level, json_logs=settings.log_json, log_file=log_file)

    translation_context = TranslationContext(
        prompt=config.get("context_prompt") or "",
        glossary=config.get("glossary") or {},
        source_lang=config.get("source_lang", "en"),
        target_lang=config.get("target_lang", "es"),
        tone=config.get("tone"),
    )

    output_mode = OutputMode(project.output_mode)
    speaker_reference_wav = config.get("speaker_reference_wav")

    request = TranslateVideoRequest(
        input_video=Path(project.input_video_path),
        output_dir=output_dir,
        context=translation_context,
        output_mode=output_mode,
        keep_original_audio_track=config.get("keep_original_audio_track", True),
        speaker_reference_wav=Path(speaker_reference_wav) if speaker_reference_wav else None,
        source_lang_hint=config.get("source_lang", "en"),
        diarize=bool(config.get("diarize", False)),
        min_speakers=config.get("min_speakers"),
        max_speakers=config.get("max_speakers"),
    )

    use_case = build_translate_video_use_case(
        settings,
        enable_dubbing=(output_mode == OutputMode.DUBBED),
        enable_diarization=request.diarize,
        resume=resume,
    )
    return use_case, request


def build_transcribe_use_case_and_request(
    project: Project,
) -> tuple[TranscribeMediaUseCase, TranscribeMediaRequest]:
    """Version delgada de `build_use_case_and_request` para el servicio de
    transcripcion standalone (`ServiceType.TRANSCRIPTION`): no hay traduccion
    ni doblaje, asi que no hace falta `TranslationContext` ni las opciones de
    diarizacion/hablantes. No soporta `resume` -- transcribir es lo bastante
    rapido para no necesitar reanudacion por checkpoint."""
    settings = load_settings()

    output_dir = Path(project.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "logs" / f"run_{datetime.now().astimezone():%Y%m%d_%H%M%S}.log"
    configure_logging(level=settings.log_level, json_logs=settings.log_json, log_file=log_file)

    config = project.config or {}
    include_summary = bool(config.get("include_summary"))
    request = TranscribeMediaRequest(
        input_media=Path(project.input_video_path),
        output_dir=output_dir,
        source_lang_hint=config.get("source_lang") or None,
        include_summary=include_summary,
    )
    use_case = build_transcribe_media_use_case(settings, include_summary=include_summary)
    return use_case, request


# Voces publicas seleccionables desde el formulario de TTS (ver
# `routers/projects.py::create_project`, campo `voice_option`). "own" no
# aparece aca: en ese caso `config['speaker_reference_wav']` ya trae la ruta
# del archivo subido, que tiene prioridad sobre este mapa.
_PUBLIC_VOICE_PATHS = {
    "public_male": PUBLIC_VOICE_MALE_WAV,
    "public_female": PUBLIC_VOICE_FEMALE_WAV,
}


def build_synthesize_use_case_and_request(
    project: Project,
) -> tuple[SynthesizeTextUseCase, SynthesizeTextRequest]:
    """Version delgada para el servicio de TTS standalone
    (`ServiceType.TTS`): el texto a sintetizar se guardo como
    `input_video_path` (ver `routers/projects.py::create_project`, mismo
    patron de "archivo de entrada" que los demas servicios). La voz de
    referencia se resuelve en este orden: (1) `config['speaker_reference_wav']`
    si el usuario subio la suya, (2) la voz publica de `config['voice_option']`
    ("public_male"/"public_female"), (3) voz publica femenina por defecto."""
    settings = load_settings()

    output_dir = Path(project.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "logs" / f"run_{datetime.now().astimezone():%Y%m%d_%H%M%S}.log"
    configure_logging(level=settings.log_level, json_logs=settings.log_json, log_file=log_file)

    config = project.config or {}
    text = Path(project.input_video_path).read_text(encoding="utf-8")
    speaker_reference_wav = config.get("speaker_reference_wav")
    voice_option = config.get("voice_option", "public_female")
    reference_wav = (
        Path(speaker_reference_wav)
        if speaker_reference_wav
        else _PUBLIC_VOICE_PATHS.get(voice_option, PUBLIC_VOICE_FEMALE_WAV)
    )

    request = SynthesizeTextRequest(
        text=text,
        output_dir=output_dir,
        language=config.get("target_lang", "es"),
        speaker_reference_wav=reference_wav,
    )
    use_case = build_synthesize_text_use_case(settings)
    return use_case, request


def build_micro_video_use_case_and_request(
    project: Project,
    db: Session,
) -> tuple[GenerateMicroVideoUseCase, GenerateMicroVideoRequest]:
    """Version delgada para el servicio de micro-video (`ServiceType.MICRO_VIDEO`):
    a diferencia de TTS, aca `input_video_path` es la imagen subida (el
    "archivo de entrada" del proyecto), no el texto -- el texto de narracion
    vive en `config['narration_text']` (ver `routers/projects.py::create_project`).
    La voz de referencia se resuelve igual que en TTS. `db` es necesaria para
    resolver la pista de musica elegida (RM-26, catalogo en BD)."""
    settings = load_settings()

    output_dir = Path(project.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    log_file = output_dir / "logs" / f"run_{datetime.now().astimezone():%Y%m%d_%H%M%S}.log"
    configure_logging(level=settings.log_level, json_logs=settings.log_json, log_file=log_file)

    config = project.config or {}
    speaker_reference_wav = config.get("speaker_reference_wav")
    voice_option = config.get("voice_option", "public_female")
    reference_wav = (
        Path(speaker_reference_wav)
        if speaker_reference_wav
        else _PUBLIC_VOICE_PATHS.get(voice_option, PUBLIC_VOICE_FEMALE_WAV)
    )

    target_duration = config.get("target_duration_seconds")
    background_music_track = config.get("background_music")
    background_music_end = config.get("background_music_end")
    additional_image_paths = config.get("additional_image_paths") or []
    image_paths = [Path(project.input_video_path), *[Path(p) for p in additional_image_paths]]
    request = GenerateMicroVideoRequest(
        images=_parse_image_adjustments(config.get("image_adjustments"), image_paths),
        text=config.get("narration_text", ""),
        output_dir=output_dir,
        language=config.get("target_lang", "es"),
        speaker_reference_wav=reference_wav,
        target_duration_seconds=float(target_duration) if target_duration else None,
        caption_bg_color=config.get("caption_bg_color", "#000000"),
        caption_highlight_style=config.get("caption_highlight_style", "background"),
        background_music_path=_resolve_background_music_path(background_music_track, db),
        background_music_start=float(config.get("background_music_start") or 0.0),
        background_music_end=float(background_music_end) if background_music_end else None,
        background_music_volume=_config_float(config, "background_music_volume", 0.12),
        narration_volume=_config_float(config, "narration_volume", 1.0),
        text_overlays=_parse_text_overlays(config.get("text_overlays")),
        caption_x=_config_float(config, "caption_x", 0.5),
        caption_y=_config_float(config, "caption_y", 0.85),
        emoji_overlays=_parse_emoji_overlays(config.get("emoji_overlays")),
    )
    use_case = build_generate_micro_video_use_case(settings)
    return use_case, request
