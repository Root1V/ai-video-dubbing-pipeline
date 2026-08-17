"""Implementacion de SpeechSynthesizer usando IndexTTS-2.5 (Bilibili/IndexTeam).

Este es el motor de sintesis de voz recomendado por defecto para doblaje: es un
modelo zero-shot con clonacion de voz a partir de una muestra corta, soporte
multilingue nativo que incluye espanol, y sobre todo **control explicito de la
duracion del habla generada** — la primera arquitectura autoregresiva que
resuelve esto de forma nativa, pensada expresamente para sincronizacion
audiovisual en doblaje de video (a diferencia de XTTS v2, que genera a ritmo
libre y depende de estirar/comprimir el audio despues con ffmpeg, degradando
timbre y prosodia cuando el ajuste es grande).

Instalacion (no esta en PyPI, se instala desde el repo oficial):
    ./scripts/setup_index_tts2.sh
lo que clona https://github.com/index-tts/index-tts en third_party/index-tts,
lo instala en modo editable, y descarga los checkpoints de
IndexTeam/IndexTTS-2.5 desde Hugging Face.

Referencia: https://github.com/index-tts/index-tts
"""

from __future__ import annotations

from pathlib import Path

from video_translator.domain.exceptions import SynthesisError
from video_translator.infrastructure.synthesis.audio_mixing import (
    concatenate_segments,
    fit_to_duration,
    wav_duration_seconds,
)
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)

# IndexTTS-2.5 espera codigos de idioma en mayusculas (EN, ES, ZH, JA, AR).
_LANG_CODE_MAP = {"es": "ES", "en": "EN", "zh": "ZH", "ja": "JA", "ar": "AR"}

# Tolerancia antes de pedirle al modelo una segunda pasada con duration_factor
# ajustado. Evita coste computacional extra cuando el desfase ya es pequeno.
_DURATION_TOLERANCE = 0.15


class IndexTTS2Synthesizer:
    def __init__(
        self,
        model_dir: str = "third_party/index-tts/checkpoints",
        cfg_path: str = "third_party/index-tts/checkpoints/config.yaml",
        use_bf16: bool = True,
        default_speaker_wav: Path | None = None,
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:
        self._model_dir = model_dir
        self._cfg_path = cfg_path
        self._use_bf16 = use_bf16
        self._default_speaker_wav = default_speaker_wav
        self._ffmpeg = ffmpeg_binary
        self._tts = None  # carga perezosa: el modelo pesa varios GB

    def _load(self):
        if self._tts is None:
            try:
                from indextts.infer_v2_5 import IndexTTS2  # type: ignore[import-not-found]
            except ImportError as exc:  # pragma: no cover
                raise SynthesisError(
                    "IndexTTS-2.5 no esta instalado. Ejecuta: ./scripts/setup_index_tts2.sh "
                    "(clona el repo oficial y descarga los checkpoints)."
                ) from exc
            logger.info("index_tts2.loading_model", model_dir=self._model_dir)
            self._tts = IndexTTS2(
                cfg_path=self._cfg_path, model_dir=self._model_dir, use_bf16=self._use_bf16
            )
        return self._tts

    def synthesize_segment(
        self,
        text: str,
        output_path: Path,
        target_duration_seconds: float,
        speaker_reference_wav: Path | None = None,
        language: str = "es",
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        speaker_wav = speaker_reference_wav or self._default_speaker_wav
        if speaker_wav is None:
            raise SynthesisError(
                "IndexTTS-2.5 requiere una muestra de voz de referencia para clonar el "
                "timbre (zero-shot). Pasa --speaker-wav con un .wav de 6-15s del hablante "
                "original."
            )

        tts = self._load()
        lang_code = _LANG_CODE_MAP.get(language.lower(), language.upper())

        try:
            # Primera pasada: generacion natural, sirve para medir el ritmo real
            # del modelo con este texto y esta voz de referencia.
            tts.infer(
                spk_audio_prompt=str(speaker_wav),
                text=text,
                lang=lang_code,
                output_path=str(output_path),
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise SynthesisError(f"Fallo sintetizando segmento con IndexTTS-2.5: {exc}") from exc

        self._refine_duration(tts, text, speaker_wav, lang_code, output_path, target_duration_seconds)
        return output_path

    def _refine_duration(
        self, tts, text: str, speaker_wav: Path, lang_code: str, output_path: Path, target_seconds: float
    ) -> None:
        """Si el desfase es significativo, regenera pidiendole al modelo un
        duration_factor mas cercano al objetivo (control nativo, preserva mejor
        la prosodia que estirar el audio despues). El residual, si queda, se
        corrige con un ajuste fino de ffmpeg como red de seguridad.
        """
        if target_seconds <= 0:
            return
        natural_duration = wav_duration_seconds(output_path)
        if natural_duration <= 0:
            return

        ratio = natural_duration / target_seconds
        if abs(ratio - 1.0) <= _DURATION_TOLERANCE:
            return  # ya esta dentro de tolerancia, no hace falta regenerar

        duration_factor = max(0.5, min(2.0, ratio))
        try:
            tts.infer(
                spk_audio_prompt=str(speaker_wav),
                text=text,
                lang=lang_code,
                output_path=str(output_path),
                duration_factor=duration_factor,
                verbose=False,
            )
        except TypeError:
            # Version del modelo sin soporte de duration_factor: nos quedamos
            # con la primera pasada y dejamos el ajuste fino de ffmpeg.
            logger.debug("index_tts2.duration_factor_unsupported")
        except Exception as exc:  # noqa: BLE001
            logger.warning("index_tts2.duration_refine_failed", error=str(exc))

        # Ajuste final de precision: fit_to_duration ahora comprime SIN TECHO
        # (encadenando atempo si hace falta) para garantizar que este clip
        # especifico encaje exacto en su hueco, priorizando conservar el
        # contenido completo del audio por sobre que no suene acelerado.
        fit_to_duration(output_path, target_seconds, ffmpeg_binary=self._ffmpeg)

    def concatenate_segments(
        self, segment_audio_paths: list[tuple[float, Path, float]], total_duration: float, output_path: Path
    ) -> Path:
        return concatenate_segments(
            segment_audio_paths, total_duration, output_path, ffmpeg_binary=self._ffmpeg
        )
