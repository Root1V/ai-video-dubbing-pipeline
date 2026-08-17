"""Contenedor de inyeccion de dependencias (composition root).

Este es el UNICO lugar del proyecto donde se conocen simultaneamente la capa
de aplicacion (casos de uso) y las implementaciones concretas de infraestructura.
Facilita cambiar de motor (p.ej. otro LLM, otro backend de TTS) editando solo
este archivo.
"""

from __future__ import annotations

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
    settings: Settings, enable_dubbing: bool = False, enable_diarization: bool = False
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
    )


def _build_synthesizer(settings: Settings):
    """Selecciona el motor de sintesis de voz para doblaje segun TTS_BACKEND.

    Import perezoso en cada rama: evita requerir las dependencias pesadas
    (torch, TTS, indextts) cuando el doblaje no se usa.
    """
    backend = settings.tts_backend.lower()
    if backend == "index_tts2":
        from video_translator.infrastructure.synthesis.index_tts2_synthesizer import (
            IndexTTS2Synthesizer,
        )

        return IndexTTS2Synthesizer(
            model_dir=settings.index_tts2_model_dir,
            cfg_path=settings.index_tts2_cfg_path,
            use_bf16=settings.index_tts2_use_bf16,
            ffmpeg_binary=settings.ffmpeg_binary,
        )
    if backend == "coqui_xtts":
        from video_translator.infrastructure.synthesis.coqui_tts_synthesizer import (
            CoquiTTSSynthesizer,
        )

        return CoquiTTSSynthesizer(
            model_name=settings.tts_model_name,
            device=settings.tts_device,
            ffmpeg_binary=settings.ffmpeg_binary,
        )
    raise ConfigurationError(
        f"TTS_BACKEND='{settings.tts_backend}' no reconocido. Usa 'index_tts2' o 'coqui_xtts'."
    )
