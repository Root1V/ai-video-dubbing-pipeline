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

import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Callable

from video_translator.application.synthesis_job import SynthesisJob
from video_translator.infrastructure.synthesis import audio_mixing
from video_translator.utils.logging_config import get_logger
from video_translator.utils.warning_collector import note_stat

logger = get_logger(__name__)

# Estado global POR PROCESO worker: cada proceso hijo tiene su propia copia
# de este modulo con su propia variable _worker_synth, cargada una sola vez
# por el initializer del pool.
_worker_synth = None


def _init_worker(factory: Callable[[], object], threads_per_worker: int) -> None:
    # Sin esto, cada proceso worker (PyTorch/BLAS) intenta usar TODOS los
    # nucleos de la maquina por defecto. Con N workers eso significa N
    # procesos compitiendo por los mismos nucleos fisicos (sobre-suscripcion
    # de hilos), que en la practica anula la ganancia del paralelismo: se
    # mide el mismo tiempo total que corriendolos en serie. Hay que fijar el
    # presupuesto de hilos ANTES de que el factory importe torch/BLAS al
    # cargar el modelo.
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[var] = str(threads_per_worker)
    try:
        import torch

        torch.set_num_threads(threads_per_worker)
    except ImportError:  # pragma: no cover - los backends de TTS siempre traen torch
        pass

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
        # Reparte los nucleos disponibles entre los workers para evitar que
        # cada uno reclame la maquina entera (ver comentario en _init_worker).
        threads_per_worker = max(1, (os.cpu_count() or self._num_workers) // self._num_workers)
        logger.info(
            "parallel_tts_pool.starting",
            num_workers=self._num_workers,
            threads_per_worker=threads_per_worker,
        )
        self._executor = ProcessPoolExecutor(
            max_workers=self._num_workers,
            initializer=_init_worker,
            initargs=(synthesizer_factory, threads_per_worker),
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
        t0 = time.monotonic()
        futures = [self._executor.submit(_worker_synthesize, job) for job in jobs]
        for future in futures:
            future.result()  # propaga excepciones y espera a que termine todo
        wall_seconds = time.monotonic() - t0
        # Latencia del lote y throughput observado desde el proceso principal.
        # (La latencia individual de cada job vive en el worker; aqui solo es
        # visible el comportamiento agregado del pool.)
        if wall_seconds > 0:
            note_stat("tts.batch_wall_seconds", round(wall_seconds, 2))
            note_stat("tts.job_avg_seconds", round(wall_seconds / len(jobs), 2))
            note_stat("tts.batch_throughput_jobs_per_second", round(len(jobs) / wall_seconds, 3))
        logger.info("parallel_tts_pool.batch_done", num_jobs=len(jobs), wall_seconds=round(wall_seconds, 2))

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
