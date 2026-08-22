"""Pool de procesos para ejecutar sintesis de voz EN PARALELO en varios
nucleos, con un modelo cargado de forma persistente en cada proceso worker
(nunca se recarga el modelo por tarea, solo una vez al arrancar cada
worker).

Por que procesos y no hilos: los motores de TTS (IndexTTS-2.5, XTTS v2) usan
PyTorch con modelos pesados; aislar cada worker en su propio proceso evita
contencion sobre un unico modelo compartido y es el patron mas robusto para
CPU-bound/GPU-bound work en Python. En una maquina con varios nucleos y RAM
de sobra (p.ej. un Apple Silicon con 128GB), repartir miles de segmentos
entre 4-8 procesos reduce el tiempo de la etapa de doblaje casi linealmente
con el numero de workers.

Este pool implementa el mismo ``SpeechSynthesizer`` Protocol (para poder
usarse como cualquier otro motor) MAS la capacidad opcional
``BatchSpeechSynthesizer.synthesize_batch``, que el caso de uso detecta con
``hasattr`` para despachar todas las tareas juntas en vez de una por una.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable

from video_translator.application.synthesis_job import SynthesisJob
from video_translator.infrastructure.synthesis import audio_mixing
from video_translator.utils.logging_config import get_logger

logger = get_logger(__name__)

# Estado global POR PROCESO worker: cada proceso hijo tiene su propia copia
# de este modulo con su propia variable _worker_synth, cargada una sola vez
# por el initializer del pool.
_worker_synth = None


def _init_worker(factory: Callable[[], object]) -> None:
    global _worker_synth
    _worker_synth = factory()


def _worker_synthesize(job: SynthesisJob) -> Path:
    global _worker_synth
    if _worker_synth is None:  # pragma: no cover - no deberia pasar nunca
        raise RuntimeError("Worker de sintesis sin modelo inicializado.")
    _worker_synth.synthesize_segment(
        text=job.text,
        output_path=job.output_path,
        target_duration_seconds=job.target_duration_seconds,
        speaker_reference_wav=job.speaker_reference_wav,
        language=job.language,
    )
    return job.output_path


class ParallelTTSPool:
    def __init__(
        self,
        synthesizer_factory: Callable[[], object],
        num_workers: int,
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:
        self._ffmpeg = ffmpeg_binary
        self._num_workers = max(1, num_workers)
        logger.info("parallel_tts_pool.starting", num_workers=self._num_workers)
        self._executor = ProcessPoolExecutor(
            max_workers=self._num_workers,
            initializer=_init_worker,
            initargs=(synthesizer_factory,),
        )

    def synthesize_segment(
        self,
        text: str,
        output_path: Path,
        target_duration_seconds: float,
        speaker_reference_wav: Path | None = None,
        language: str = "es",
    ) -> Path:
        """Cumple el Protocol SpeechSynthesizer estandar (una tarea a la vez),
        por si algo llama a este metodo directamente en vez de synthesize_batch."""
        job = SynthesisJob(
            output_path=output_path,
            text=text,
            target_duration_seconds=target_duration_seconds,
            speaker_reference_wav=speaker_reference_wav,
            language=language,
            start_seconds=0.0,
            max_duration_seconds=target_duration_seconds,
        )
        return self._executor.submit(_worker_synthesize, job).result()

    def synthesize_batch(self, jobs: list[SynthesisJob]) -> None:
        if not jobs:
            return
        logger.info("parallel_tts_pool.batch_start", num_jobs=len(jobs), num_workers=self._num_workers)
        futures = [self._executor.submit(_worker_synthesize, job) for job in jobs]
        for future in futures:
            future.result()  # propaga excepciones y espera a que termine todo
        logger.info("parallel_tts_pool.batch_done", num_jobs=len(jobs))

    def concatenate_segments(
        self, segment_audio_paths: list[tuple[float, Path, float]], total_duration: float, output_path: Path
    ) -> Path:
        # Operacion barata (solo ffmpeg, sin modelo de IA): no hace falta
        # despacharla a un worker, se ejecuta directo en el proceso principal.
        return audio_mixing.concatenate_segments(
            segment_audio_paths, total_duration, output_path, ffmpeg_binary=self._ffmpeg
        )

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)
