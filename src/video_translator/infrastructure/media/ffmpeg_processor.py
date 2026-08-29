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
        cmd = [
            self._ffmpeg, "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_path),
        ]
        self._run(cmd, error_cls=MuxingError)
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
