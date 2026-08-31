"""Implementacion concreta de MediaProcessor usando los binarios ffmpeg/ffprobe.

Se invoca ffmpeg via subprocess en lugar de decodificar en Python puro: es la
opcion mas robusta y eficiente para archivos de video largos (>1h), y es el
estandar de facto open source para este tipo de operaciones.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from video_translator.domain.exceptions import AudioExtractionError, MuxingError
from video_translator.infrastructure.synthesis.audio_mixing import fit_to_duration
from video_translator.utils.logging_config import get_logger
from video_translator.utils.warning_collector import increment_counter

logger = get_logger(__name__)


class FFmpegMediaProcessor:
    def __init__(
        self,
        ffmpeg_binary: str = "ffmpeg",
        ffprobe_binary: str = "ffprobe",
        audio_sample_rate: int = 16000,
    ) -> None:
        self._ffmpeg = ffmpeg_binary
        self._ffprobe = ffprobe_binary
        self._sample_rate = audio_sample_rate

    def get_duration_seconds(self, media_path: Path) -> float:
        cmd = [
            self._ffprobe,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(media_path),
        ]
        result = self._run(cmd, error_cls=AudioExtractionError)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])

    def extract_audio(self, video_path: Path, output_wav: Path) -> Path:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(self._sample_rate),
            "-ac", "1",
            str(output_wav),
        ]
        self._run(cmd, error_cls=AudioExtractionError)
        if not output_wav.exists():
            raise AudioExtractionError(f"ffmpeg no genero el archivo de salida: {output_wav}")
        return output_wav

    def extract_audio_clip(self, audio_path: Path, start: float, end: float, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.1, end - start)
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(audio_path),
            "-ss", str(max(0.0, start)),
            "-t", str(duration),
            "-acodec", "pcm_s16le",
            "-ar", str(self._sample_rate),
            "-ac", "1",
            str(output_path),
        ]
        self._run(cmd, error_cls=AudioExtractionError)
        return output_path

    def burn_subtitles(self, video_path: Path, srt_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # ffmpeg requiere escapar los ':' de rutas Windows y caracteres especiales del filtro.
        srt_filter_path = str(srt_path).replace("\\", "/").replace(":", "\\:")
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", f"subtitles='{srt_filter_path}'",
            "-c:a", "copy",
            str(output_path),
        ]
        self._run(cmd, error_cls=MuxingError)
        return output_path

    def render_ass_captions(self, video_path: Path, ass_path: Path, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ass_filter_path = str(ass_path).replace("\\", "/").replace(":", "\\:")
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-vf", f"ass='{ass_filter_path}'",
            "-c:a", "copy",
            str(output_path),
        ]
        self._run(cmd, error_cls=MuxingError)
        return output_path

    def attach_soft_subtitles(
        self, video_path: Path, srt_path: Path, output_path: Path, lang_code: str = "spa"
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(video_path),
            "-i", str(srt_path),
            "-map", "0",
            "-map", "1",
            "-c", "copy",
            "-c:s", "mov_text",
            "-metadata:s:s:0", f"language={lang_code}",
            str(output_path),
        ]
        self._run(cmd, error_cls=MuxingError)
        return output_path

    def replace_audio_track(
        self,
        video_path: Path,
        new_audio_path: Path,
        output_path: Path,
        keep_original_as_secondary: bool = True,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if keep_original_as_secondary:
            cmd = [
                self._ffmpeg, "-y",
                "-i", str(video_path),
                "-i", str(new_audio_path),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-map", "0:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-metadata:s:a:0", "title=Español (doblaje)",
                "-metadata:s:a:0", "language=spa",
                "-metadata:s:a:1", "title=Original",
                "-metadata:s:a:1", "language=eng",
                str(output_path),
            ]
        else:
            cmd = [
                self._ffmpeg, "-y",
                "-i", str(video_path),
                "-i", str(new_audio_path),
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "copy",
                "-c:a", "aac",
                "-metadata:s:a:0", "language=spa",
                str(output_path),
            ]
        self._run(cmd, error_cls=MuxingError)
        return output_path

    def render_image_video(
        self,
        image_path: Path,
        audio_path: Path,
        output_path: Path,
        duration_seconds: float,
        width: int = 1080,
        height: int = 1920,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fps = 30
        total_frames = max(1, round(duration_seconds * fps))
        # 1) scale+crop a exactamente widthxheight (cubre el encuadre, recorta
        #    el sobrante centrado) para que la imagen de entrada -- de
        #    cualquier orientacion/aspecto -- no se deforme. 2) zoompan sobre
        #    ese frame ya normalizado: como su propio iw:ih coincide con
        #    width:height, el zoom/crop interno no distorsiona tampoco.
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"zoompan=z='min(zoom+0.0008,1.3)':d={total_frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps},"
            f"format=yuv420p"
        )
        # Sin "-shortest": si el audio dura menos que `duration_seconds` (el
        # caller puede pedir un video mas largo que la narracion a proposito
        # -- duracion fija elegida por el usuario, Ken Burns sigue corriendo
        # en silencio el resto del tiempo) no debe recortarse al largo del
        # audio. PERO probado en la practica: sin un limite EXPLICITO de
        # duracion, la imagen en loop ("-loop 1", tecnicamente infinita)
        # combinada con zoompan puede seguir generando frames mucho mas alla
        # de lo esperado en vez de detenerse en `d=total_frames` -- "-t"
        # fuerza un corte duro de la salida en `duration_seconds` sin
        # importar el comportamiento de los streams de entrada.
        cmd = [
            self._ffmpeg, "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-vf", vf,
            "-t", str(duration_seconds),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path),
        ]
        self._run(cmd, error_cls=MuxingError)
        return output_path

    def fit_audio_to_duration(self, audio_path: Path, target_seconds: float) -> bool:
        return fit_to_duration(audio_path, target_seconds, ffmpeg_binary=self._ffmpeg)

    def mix_background_music(
        self,
        narration_path: Path,
        music_path: Path,
        output_path: Path,
        duration_seconds: float,
        music_volume: float = 0.12,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # "-stream_loop -1" repite la musica indefinidamente -- sin esto una
        # pista mas corta que el video se cortaria a mitad de la reproduccion
        # en vez de acompañar todo el video. "-t" (como en render_image_video)
        # pone un tope duro: sin el, un input en loop infinito puede dejar a
        # ffmpeg generando audio mucho mas alla de lo esperado. Ambas pistas
        # se normalizan a la misma tasa/canales antes de mezclar para evitar
        # artefactos cuando difieren (narracion mono 22050Hz, musica stereo
        # 44100Hz tipicamente).
        filter_complex = (
            f"[0:a]volume={music_volume},aformat=sample_rates=44100:channel_layouts=stereo[music];"
            "[1:a]aformat=sample_rates=44100:channel_layouts=stereo[narr];"
            "[narr][music]amix=inputs=2:duration=longest:dropout_transition=0[aout]"
        )
        cmd = [
            self._ffmpeg, "-y",
            "-stream_loop", "-1",
            "-i", str(music_path),
            "-i", str(narration_path),
            "-filter_complex", filter_complex,
            "-map", "[aout]",
            "-t", str(duration_seconds),
            str(output_path),
        ]
        self._run(cmd, error_cls=MuxingError)
        return output_path

    def clean_music_track(self, input_path: Path, output_wav: Path) -> Path:
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        # silenceremove analiza el nivel de audio y recorta el silencio inicial
        # (start_periods=1, un solo recorte al comienzo) por debajo de -50dB
        # sostenido 0.1s -- suficiente para sacar el aire muerto al inicio de
        # una pista sin comerse el ataque real de la musica. 44.1kHz estereo
        # (no self._sample_rate, pensado para voz/STT) para no degradar la
        # calidad de una pista musical -- misma tasa a la que ya se normaliza
        # en mix_background_music.
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(input_path),
            "-af", "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1",
            "-ar", "44100",
            "-ac", "2",
            str(output_wav),
        ]
        self._run(cmd, error_cls=AudioExtractionError)
        return output_wav

    def extract_music_range(self, track_path: Path, start: float, end: float, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.1, end - start)
        cmd = [
            self._ffmpeg, "-y",
            "-i", str(track_path),
            "-ss", str(max(0.0, start)),
            "-t", str(duration),
            "-ar", "44100",
            "-ac", "2",
            str(output_path),
        ]
        self._run(cmd, error_cls=AudioExtractionError)
        return output_path

    def _run(self, cmd: list[str], error_cls: type[Exception]) -> subprocess.CompletedProcess:
        logger.debug("ffmpeg.exec", cmd=" ".join(cmd))
        increment_counter("ffmpeg.calls")
        try:
            return subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise error_cls(
                f"No se encontro el binario '{cmd[0]}'. Instala ffmpeg y verifica el PATH."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise error_cls(f"Fallo ejecutando '{cmd[0]}': {exc.stderr}") from exc
