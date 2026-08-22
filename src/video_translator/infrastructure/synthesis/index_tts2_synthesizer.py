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

RENDIMIENTO — una sola pasada de inferencia por segmento:
Una version anterior generaba primero "a ritmo natural", media la duracion
resultante, y si se alejaba demasiado del objetivo, volvia a generar una
SEGUNDA vez con un duration_factor corregido — hasta el doble de inferencias
del modelo (el paso mas caro de todo el pipeline) por cada segmento. Ahora se
estima el duration_factor de antemano con una heuristica de caracteres por
segundo (sin necesidad de generar nada primero), se genera UNA sola vez, y el
ajuste fino final (si el resultado no encaja exacto) lo hace ffmpeg
(``fit_to_duration``, barato, sin techo de compresion) en vez del modelo. En
un video con miles de segmentos esto es la diferencia entre horas y minutos.
"""

from __future__ import annotations

from pathlib import Path

from video_translator.domain.exceptions import SynthesisError
from video_translator.infrastructure.synthesis.audio_mixing import (
    concatenate_segments,
    fit_to_duration,
)
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)

# IndexTTS-2.5 espera codigos de idioma en mayusculas (EN, ES, ZH, JA, AR).
_LANG_CODE_MAP = {"es": "ES", "en": "EN", "zh": "ZH", "ja": "JA", "ar": "AR"}

# Heuristica de ritmo de habla en espanol (caracteres por segundo), usada
# SOLO para estimar un duration_factor razonable de entrada sin tener que
# generar audio primero para medirlo. No necesita ser exacta: el ajuste fino
# final lo hace ffmpeg de todas formas.
_CHARS_PER_SECOND_ES = 15.0

# Rango de duration_factor que el modelo soporta de forma nativa.
_MIN_DURATION_FACTOR = 0.5
_MAX_DURATION_FACTOR = 2.0


class IndexTTS2Synthesizer:
    def __init__(
        self,
        model_dir: str = "third_party/index-tts/checkpoints",
        cfg_path: str = "third_party/index-tts/checkpoints/config.yaml",
        use_bf16: bool = True,
        default_speaker_wav: Path | None = None,
        ffmpeg_binary: str = "ffmpeg",
        device: str | None = None,
        use_torch_compile: bool = False,
        num_beams: int = 3,
    ) -> None:
        self._model_dir = model_dir
        self._cfg_path = cfg_path
        self._use_bf16 = use_bf16
        self._default_speaker_wav = default_speaker_wav
        self._ffmpeg = ffmpeg_binary
        # None = dejar que IndexTTS2 autodetecte (cuda > mps > cpu). Se puede
        # forzar explicitamente (p.ej. "cpu") — importante en macOS cuando se
        # corren varios workers en paralelo, ver container.py: varios
        # procesos tomando Metal (MPS) a la vez es una combinacion inestable
        # que puede crashear el driver de GPU y reiniciar el sistema.
        self._device = device
        # Compila el sub-modelo s2mel (difusion, no autoregresivo) con
        # torch.compile -- mismos pesos, mismo calculo, sin perdida de
        # calidad. Ya viene cableado dentro de IndexTTS2 (enable_torch_compile
        # en su constructor) pero apagado por defecto ahi tambien. Paga un
        # costo de compilacion la primera inferencia de cada proceso worker;
        # solo conviene si el proceso sintetiza suficientes segmentos para
        # amortizarlo.
        self._use_torch_compile = use_torch_compile
        # El GPT autoregresivo usa num_beams=3 por defecto internamente (no
        # expuesto en el README). Probado en CPU: bajarlo a 1 no acelero
        # gpt_gen_time (HuggingFace generate() procesa los beams como
        # dimension de batch en un solo forward pass, casi gratis con margen
        # de CPU libre) -- no hay razon para bajarlo, arriesgaria calidad sin
        # ganar velocidad. Configurable solo por si acaso en otro hardware.
        self._num_beams = num_beams
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
            logger.info(
                "index_tts2.loading_model",
                model_dir=self._model_dir,
                device=self._device or "auto",
                use_torch_compile=self._use_torch_compile,
            )
            kwargs = {"device": self._device} if self._device else {}
            self._tts = IndexTTS2(
                cfg_path=self._cfg_path,
                model_dir=self._model_dir,
                use_bf16=self._use_bf16,
                use_torch_compile=self._use_torch_compile,
                **kwargs,
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
        duration_factor = self._estimate_duration_factor(text, target_duration_seconds)

        try:
            kwargs = {"duration_factor": duration_factor} if duration_factor is not None else {}
            tts.infer(
                spk_audio_prompt=str(speaker_wav),
                text=text,
                lang=lang_code,
                output_path=str(output_path),
                verbose=False,
                num_beams=self._num_beams,
                **kwargs,
            )
        except TypeError:
            # Version del modelo instalada sin soporte de duration_factor:
            # reintenta sin el (sigue siendo UNA sola pasada de inferencia).
            logger.debug("index_tts2.duration_factor_unsupported")
            try:
                tts.infer(
                    spk_audio_prompt=str(speaker_wav),
                    text=text,
                    lang=lang_code,
                    output_path=str(output_path),
                    verbose=False,
                    num_beams=self._num_beams,
                )
            except Exception as exc:  # noqa: BLE001
                raise SynthesisError(f"Fallo sintetizando segmento con IndexTTS-2.5: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise SynthesisError(f"Fallo sintetizando segmento con IndexTTS-2.5: {exc}") from exc

        # Ajuste final de precision: ffmpeg (barato, sin techo de compresion),
        # no una segunda pasada del modelo. Ver docstring del modulo.
        fit_to_duration(output_path, target_duration_seconds, ffmpeg_binary=self._ffmpeg)
        return output_path

    @staticmethod
    def _estimate_duration_factor(text: str, target_seconds: float) -> float | None:
        """Estima un duration_factor de entrada sin generar audio primero,
        a partir de la longitud del texto. No necesita ser precisa: solo le
        da al modelo un punto de partida razonable para que ffmpeg tenga
        menos que corregir despues (mejor calidad que partir siempre de 1.0)."""
        if target_seconds <= 0:
            return None
        estimated_natural_seconds = len(text) / _CHARS_PER_SECOND_ES
        if estimated_natural_seconds <= 0:
            return None
        factor = estimated_natural_seconds / target_seconds
        return max(_MIN_DURATION_FACTOR, min(_MAX_DURATION_FACTOR, factor))

    def concatenate_segments(
        self, segment_audio_paths: list[tuple[float, Path, float]], total_duration: float, output_path: Path
    ) -> Path:
        return concatenate_segments(
            segment_audio_paths, total_duration, output_path, ffmpeg_binary=self._ffmpeg
        )
