"""Traduce un `Project` (fila de BD) a los objetos de entrada del pipeline real.

Replica exactamente la receta de `cli.py::translate` (carga de `Settings`,
overrides puntuales, `TranslationContext`/`TranslateVideoRequest`, logging por
corrida) para que la tarea Celery sea ese mismo camino sin la parte de
consola. No se modifica `application`/`domain`: esto es un adaptador nuevo,
igual que `cli.py` es "otro driver" del mismo caso de uso.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from video_translator.application.use_cases.translate_video import TranslateVideoUseCase
from video_translator.config import load_settings
from video_translator.container import build_translate_video_use_case
from video_translator.domain.models import OutputMode, TranslateVideoRequest, TranslationContext
from video_translator.utils.logging_config import configure_logging
from video_translator.web.db.models import Project


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
