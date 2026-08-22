"""Contenedor de inyeccion de dependencias (composition root).

Este es el UNICO lugar del proyecto donde se conocen simultaneamente la capa
de aplicacion (casos de uso) y las implementaciones concretas de infraestructura.
Facilita cambiar de motor (p.ej. otro LLM, otro backend de TTS) editando solo
este archivo.
"""

from __future__ import annotations

import os
import platform
from functools import partial
from typing import Callable

from video_translator.application.use_cases.translate_video import TranslateVideoUseCase
from video_translator.config import Settings
from video_translator.domain.exceptions import ConfigurationError
from video_translator.infrastructure.media.ffmpeg_processor import FFmpegMediaProcessor
from video_translator.infrastructure.subtitles.srt_writer import SrtSubtitleWriter
from video_translator.infrastructure.transcription.faster_whisper_transcriber import (
    FasterWhisperTranscriber,
)
from video_translator.infrastructure.translation.llama_server_translator import (
    LlamaServerTranslator,
)
from video_translator.infrastructure.translation.ollama_translator import OllamaTranslator
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)

# Tope de workers paralelos auto-detectados: cada uno carga su propia copia
# del modelo de TTS en memoria, asi que crear tantos como nucleos haya suele
# ser contraproducente (satura RAM/ancho de banda de memoria antes que CPU).
_AUTO_MAX_TTS_WORKERS = 6


def _build_translator(settings: Settings):
    """Selecciona el adaptador de traduccion segun TRANSLATION_BACKEND.

    Ambos adaptadores implementan el mismo Protocol ``Translator``, por lo que
    el resto del pipeline (TranslateVideoUseCase) no necesita saber cual se usa.
    """
    backend = settings.translation_backend.lower()
    if backend == "ollama":
        return OllamaTranslator(
            host=settings.ollama_host,
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
    if backend == "llama_server":
        return LlamaServerTranslator(
            host=settings.llama_server_host,
            model=settings.llama_server_model,
            temperature=settings.ollama_temperature,
            timeout_seconds=settings.ollama_timeout_seconds,
            max_tokens=settings.llama_server_max_tokens,
            api_key=settings.llama_server_api_key,
        )
    raise ConfigurationError(
        f"TRANSLATION_BACKEND='{settings.translation_backend}' no reconocido. "
        "Usa 'ollama' o 'llama_server'."
    )


def build_translate_video_use_case(
    settings: Settings,
    enable_dubbing: bool = False,
    enable_diarization: bool = False,
    resume: bool = False,
) -> TranslateVideoUseCase:
    media_processor = FFmpegMediaProcessor(
        ffmpeg_binary=settings.ffmpeg_binary,
        ffprobe_binary=settings.ffprobe_binary,
        audio_sample_rate=settings.audio_sample_rate,
    )
    transcriber = FasterWhisperTranscriber(
        model_size=settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
        beam_size=settings.whisper_beam_size,
        vad_filter=settings.whisper_vad_filter,
        cpu_threads=settings.whisper_cpu_threads,
        num_workers=settings.whisper_num_workers,
    )
    translator = _build_translator(settings)
    subtitle_writer = SrtSubtitleWriter()

    speech_synthesizer = None
    if enable_dubbing:
        speech_synthesizer = _build_synthesizer(settings)

    speaker_diarizer = None
    gender_classifier = None
    if enable_diarization:
        from video_translator.infrastructure.diarization.subprocess_diarizer import (
            SubprocessDiarizer,
        )

        speaker_diarizer = SubprocessDiarizer(
            python_bin=settings.diarization_python_bin,
            worker_script=settings.diarization_worker_script,
            model_name=settings.diarization_model,
            hf_token=settings.hf_token,
            device=settings.diarization_device,
            dyld_library_path=settings.diarization_dyld_library_path,
        )
        if settings.gender_detection_enabled:
            from video_translator.infrastructure.diarization.subprocess_gender_classifier import (
                SubprocessGenderClassifier,
            )

            gender_classifier = SubprocessGenderClassifier(
                python_bin=settings.diarization_python_bin,
                worker_script=settings.diarization_worker_script,
            )

    return TranslateVideoUseCase(
        media_processor=media_processor,
        transcriber=transcriber,
        translator=translator,
        subtitle_writer=subtitle_writer,
        speech_synthesizer=speech_synthesizer,
        speaker_diarizer=speaker_diarizer,
        gender_classifier=gender_classifier,
        translation_batch_max_chars=settings.translation_batch_max_chars,
        context_window_segments=settings.translation_context_window_segments,
        group_segments_for_synthesis=settings.tts_group_segments,
        group_max_gap_seconds=settings.tts_group_max_gap_seconds,
        group_max_chars=settings.tts_group_max_chars,
        resume=resume,
    )


def _synthesizer_factory(settings: Settings, num_workers: int) -> Callable[[], object]:
    """Devuelve una funcion SIN ARGUMENTOS que construye una instancia nueva
    del motor de TTS configurado.

    Se usa tanto para construir directamente (modo secuencial, un solo
    proceso) como para pasarsela a ``ParallelTTSPool``, que la ejecuta una
    vez POR CADA proceso worker (cada worker termina con su propia copia del
    modelo cargada en memoria, no se comparte entre procesos). Debe ser
    "picklable" para poder cruzar el limite de proceso; ``functools.partial``
    sobre una clase con argumentos simples (str/bool) lo es.
    """
    backend = settings.tts_backend.lower()
    if backend == "index_tts2":
        from video_translator.infrastructure.synthesis.index_tts2_synthesizer import (
            IndexTTS2Synthesizer,
        )

        device = settings.index_tts2_device or None
        if device is None and num_workers > 1 and platform.system() == "Darwin":
            # SEGURIDAD: IndexTTS2 autodetecta MPS (Metal) si no se le dice
            # lo contrario. Varios PROCESOS tomando Metal a la vez de forma
            # concurrente es una combinacion conocida por ser inestable en
            # macOS — puede crashear el driver de GPU y reiniciar el sistema
            # por completo (no es un simple error de Python). Se fuerza CPU
            # automaticamente para los workers paralelos en Mac, salvo que
            # el usuario fije INDEX_TTS2_DEVICE explicitamente (bajo su
            # propio riesgo). Con un solo worker (num_workers<=1) no aplica:
            # MPS en un unico proceso es el uso soportado oficialmente.
            device = "cpu"
            logger.warning(
                "container.forcing_cpu_for_parallel_tts_on_macos",
                num_workers=num_workers,
                reason=(
                    "Varios procesos usando Metal (MPS) a la vez pueden crashear el driver "
                    "de GPU en macOS y reiniciar el sistema. Se fuerza CPU para los workers "
                    "paralelos. Para usar GPU, corre con --tts-workers 1, o fija "
                    "INDEX_TTS2_DEVICE=mps explicitamente si aceptas el riesgo."
                ),
            )

        return partial(
            IndexTTS2Synthesizer,
            model_dir=settings.index_tts2_model_dir,
            cfg_path=settings.index_tts2_cfg_path,
            use_bf16=settings.index_tts2_use_bf16,
            ffmpeg_binary=settings.ffmpeg_binary,
            device=device,
        )
    if backend == "coqui_xtts":
        from video_translator.infrastructure.synthesis.coqui_tts_synthesizer import (
            CoquiTTSSynthesizer,
        )

        return partial(
            CoquiTTSSynthesizer,
            model_name=settings.tts_model_name,
            device=settings.tts_device,
            ffmpeg_binary=settings.ffmpeg_binary,
        )
    raise ConfigurationError(
        f"TTS_BACKEND='{settings.tts_backend}' no reconocido. Usa 'index_tts2' o 'coqui_xtts'."
    )


def _resolve_tts_worker_count(configured: int) -> int:
    """0/negativo = auto-detectar: mitad de los nucleos disponibles, con un
    tope (cada worker carga su propia copia del modelo en memoria)."""
    if configured > 0:
        return configured
    cpu_count = os.cpu_count() or 4
    return max(1, min(_AUTO_MAX_TTS_WORKERS, cpu_count // 2))


def _build_synthesizer(settings: Settings):
    """Construye el motor de TTS para doblaje segun TTS_BACKEND, envuelto en
    un pool de procesos paralelos si TTS_PARALLEL_WORKERS lo amerita.

    Import perezoso en cada rama: evita requerir las dependencias pesadas
    (torch, TTS, indextts) cuando el doblaje no se usa.
    """
    num_workers = _resolve_tts_worker_count(settings.tts_parallel_workers)
    factory = _synthesizer_factory(settings, num_workers)

    if num_workers <= 1:
        return factory()

    from video_translator.infrastructure.synthesis.parallel_tts_pool import ParallelTTSPool

    return ParallelTTSPool(
        synthesizer_factory=factory, num_workers=num_workers, ffmpeg_binary=settings.ffmpeg_binary
    )
