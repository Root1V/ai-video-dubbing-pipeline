"""Utilidades de audio compartidas entre los distintos backends de sintesis de voz.

Tanto IndexTTS2Synthesizer como CoquiTTSSynthesizer necesitan: (a) medir la
duracion de un .wav generado y (b) componer la pista final ubicando cada
segmento sintetizado en su timestamp original dentro del video. Esta logica
es identica sin importar que modelo genero el audio, asi que vive aqui para
no duplicarla.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

from video_translator.domain.exceptions import SynthesisError
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)


def wav_duration_seconds(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as f:
        frames = f.getnframes()
        rate = f.getframerate()
        return frames / float(rate)


# Por debajo de este factor no vale la pena reprocesar el audio (la diferencia
# es inaudible) y se evita el costo de un pase extra de ffmpeg.
_NEAR_ENOUGH_TOLERANCE = 0.03

# Si el clip YA es mas corto que su hueco no hay riesgo de solapamiento; solo
# se alarga levemente (nunca mas alla de este piso) para no sonar estirado de
# forma artificial. Este es el UNICO limite que queda: del lado de comprimir
# (acelerar) no hay techo, porque preservar el contenido completo del audio
# importa mas que evitar que suene acelerado (ver _build_atempo_chain).
_MIN_SLOWDOWN_FACTOR = 0.75


def _build_atempo_chain(factor: float) -> list[float]:
    """Descompone un factor de velocidad arbitrario en una cadena de valores
    validos para ``atempo`` (ffmpeg limita cada instancia a un maximo
    razonable antes de empezar a saltar muestras en vez de mezclarlas; la
    propia documentacion de ffmpeg recomienda encadenar varias instancias
    para factores grandes en vez de pasar un solo valor alto). Esto permite
    comprimir un clip TANTO como haga falta para que nunca haga falta
    recortarlo, sin importar que tan largo haya quedado.
    """
    if factor <= 0:
        return [1.0]

    stages: list[float] = []
    remaining = factor
    if remaining > 2.0:
        while remaining > 2.0:
            stages.append(2.0)
            remaining /= 2.0
        stages.append(remaining)
    elif remaining < 0.5:
        while remaining < 0.5:
            stages.append(0.5)
            remaining /= 0.5
        stages.append(remaining)
    else:
        stages.append(remaining)
    return stages


def fit_to_duration(wav_path: Path, target_seconds: float, ffmpeg_binary: str = "ffmpeg") -> bool:
    """Ajusta la velocidad de ESTE clip especifico para que encaje en su
    propio hueco disponible (``target_seconds``).

    El factor de velocidad se calcula de forma independiente para cada
    llamada (``duracion_actual_de_este_clip / target_seconds_de_este_clip``),
    nunca un valor fijo compartido entre segmentos — cada linea de dialogo
    puede necesitar una compresion distinta segun cuanto se paso su propio
    hueco.

    Prioriza SIEMPRE preservar el contenido completo del audio: si hace falta
    comprimir (acelerar), se aplica el factor completo necesario, encadenando
    varias etapas de ``atempo`` si supera lo que admite una sola instancia —
    mejor que la voz suene mas rapida en ese tramo a perder parte de lo dicho
    con un recorte. Solo del lado de alargar (clip mas corto que su hueco, sin
    riesgo de solapamiento) se limita el ajuste, para no sonar innecesariamente
    estirado.

    Devuelve True si el ajuste se aplico correctamente (o no hacia falta),
    False si fallo la llamada a ffmpeg (el archivo original queda intacto en
    ese caso).
    """
    if target_seconds <= 0:
        return True
    current = wav_duration_seconds(wav_path)
    if current <= 0:
        return True

    speed_factor = current / target_seconds
    if speed_factor > 1.0:
        # Hace falta comprimir: se aplica el factor completo, sin techo.
        applied_factor = speed_factor
    else:
        # El clip ya entra en su hueco; alargar solo un poco como mucho.
        applied_factor = max(_MIN_SLOWDOWN_FACTOR, speed_factor)

    if abs(applied_factor - 1.0) < _NEAR_ENOUGH_TOLERANCE:
        return True

    chain = _build_atempo_chain(applied_factor)
    filter_str = ",".join(f"atempo={stage:.4f}" for stage in chain)

    tmp_path = wav_path.with_suffix(".tmp.wav")
    cmd = [ffmpeg_binary, "-y", "-i", str(wav_path), "-filter:a", filter_str, str(tmp_path)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        tmp_path.replace(wav_path)
    except subprocess.CalledProcessError as exc:
        logger.warning(
            "audio_mixing.fit_duration_failed",
            error=exc.stderr,
            requested_factor=round(applied_factor, 2),
        )
        return False

    if applied_factor > 2.2:
        # Informativo: compresion fuerte aplicada a este segmento en
        # particular. No es un error, solo conviene saber cuando pasa (p.ej.
        # para revisar si conviene pedir traducciones mas breves via --context).
        logger.info(
            "audio_mixing.strong_compression_applied",
            path=str(wav_path),
            factor=round(applied_factor, 2),
        )
    return True


def concatenate_segments(
    segment_audio_paths: list[tuple[float, Path, float]],
    total_duration: float,
    output_path: Path,
    ffmpeg_binary: str = "ffmpeg",
) -> Path:
    """Compone la pista final ubicando cada .wav en su timestamp (adelay+amix).

    Cada tupla es ``(start_seconds, path, max_duration_seconds)``. ``max_duration_seconds``
    es el hueco real disponible antes de que empiece el siguiente segmento (o
    antes del final del video, para el ultimo).

    En operacion normal, cada clip ya deberia encajar en su hueco: la
    compresion de velocidad (``fit_to_duration``) se aplica ANTES, por
    segmento, sin techo, precisamente para que esto nunca haga falta. El
    recorte (``atrim``) que sigue aqui es una red de seguridad para el caso
    verdaderamente anomalo de que esa compresion haya fallado (p.ej. error de
    ffmpeg al procesar un clip puntual) — no la via normal para lotes largos.
    Si llega a activarse, se registra como advertencia (algo salio mal antes,
    no es comportamiento esperado) y se le agrega un fundido de salida corto
    (~80ms) para que el corte suene como la voz apagandose, no como un tajo
    seco a media palabra.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not segment_audio_paths:
        raise SynthesisError("No hay segmentos de audio para concatenar.")

    inputs: list[str] = []
    filter_parts: list[str] = []
    for i, (start_seconds, path, max_duration_seconds) in enumerate(segment_audio_paths):
        inputs += ["-i", str(path)]
        delay_ms = max(0, int(start_seconds * 1000))
        natural_duration = wav_duration_seconds(path)

        # Pequeno margen (20ms) para no recortar por diferencias de redondeo.
        if natural_duration > max_duration_seconds + 0.02:
            trim_seconds = max(0.05, max_duration_seconds)
            fade_duration = min(0.08, trim_seconds / 4)
            fade_start = max(0.0, trim_seconds - fade_duration)
            filter_parts.append(
                f"[{i}:a]atrim=start=0:end={trim_seconds:.3f},"
                f"afade=t=out:st={fade_start:.3f}:d={fade_duration:.3f},"
                f"asetpts=PTS-STARTPTS,adelay={delay_ms}|{delay_ms}[a{i}]"
            )
            logger.warning(
                "audio_mixing.unexpected_overflow_after_compression",
                index=i,
                natural_seconds=round(natural_duration, 2),
                available_seconds=round(max_duration_seconds, 2),
                overflow_seconds=round(natural_duration - max_duration_seconds, 2),
                hint="la compresion de velocidad deberia haber evitado esto; "
                     "revisa si fit_to_duration fallo para este segmento",
            )
        else:
            filter_parts.append(
                f"[{i}:a]asetpts=PTS-STARTPTS,adelay={delay_ms}|{delay_ms}[a{i}]"
            )

    mix_inputs = "".join(f"[a{i}]" for i in range(len(segment_audio_paths)))
    filter_complex = (
        ";".join(filter_parts)
        + f";{mix_inputs}amix=inputs={len(segment_audio_paths)}:normalize=0[out]"
    )

    cmd = [
        ffmpeg_binary, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(total_duration),
        str(output_path),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise SynthesisError(f"Fallo componiendo pista de doblaje: {exc.stderr}") from exc
    return output_path
