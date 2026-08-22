"""Colector de advertencias del pipeline (process-local).

La infraestructura (mezcla de audio, contenedor, etc.) emite warnings que hoy
solo viven en el log; este modulo permite que cualquiera de ellos quede tambien
registrado en `pipeline_timings.json` via `PipelineTimings.add_warning`.

Es process-local a proposito: los workers de TTS paralelo son procesos aparte
(sus warnings no cruzan aqui), pero todo el codigo que corre en el proceso
principal — mezcla, muxing, container — si comparte este registro.
"""

from __future__ import annotations

import statistics
import threading
from datetime import datetime, timezone

_LOCK = threading.Lock()
_WARNINGS: list[dict] = []
_STATS: dict[str, list] = {}
_COUNTERS: dict[str, int] = {}


def note_warning(source: str, **details: object) -> None:
    """Registra una advertencia para el reporte de timings."""
    entry: dict[str, object] = {
        "source": source,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    entry.update(details)
    with _LOCK:
        _WARNINGS.append(entry)


def drain_warnings() -> list[dict]:
    """Devuelve y limpia las advertencias acumuladas hasta ahora."""
    with _LOCK:
        out, _WARNINGS[:] = list(_WARNINGS), []
        return out


def note_stat(key: str, value: object) -> None:
    """Acumula un valor bajo una clave (p.ej. duracion de un job de TTS)."""
    with _LOCK:
        _STATS.setdefault(key, []).append(value)


def increment_counter(key: str, by: int = 1) -> None:
    """Incrementa un contador simple (p.ej. invocaciones de ffmpeg)."""
    with _LOCK:
        _COUNTERS[key] = _COUNTERS.get(key, 0) + by


def drain_stats() -> tuple[dict[str, list], dict[str, int]]:
    """Devuelve y limpia (stats, counters) acumulados hasta ahora."""
    with _LOCK:
        stats = dict(_STATS)
        counters = dict(_COUNTERS)
        _STATS.clear()
        _COUNTERS.clear()
        return stats, counters


def summarize(values: list) -> dict:
    """Resumen tipico de una lista de duraciones: min/median/max/sum."""
    if not values:
        return {}
    nums = [float(v) for v in values]
    return {
        "min": round(min(nums), 2),
        "median": round(statistics.median(nums), 2),
        "max": round(max(nums), 2),
        "sum": round(sum(nums), 2),
        "mean": round(statistics.fmean(nums), 2),
    }
