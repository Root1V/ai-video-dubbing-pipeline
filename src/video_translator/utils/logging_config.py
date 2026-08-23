"""Configuracion centralizada de logging usando structlog.

Se expone una unica funcion ``configure_logging`` para que tanto el CLI como
las pruebas de integracion inicialicen el logging de forma consistente.

Cuando se pasa ``log_file``, CADA linea que se ve en la consola tambien se
escribe a ese archivo (sin codigos de color ANSI, para que quede legible en
un editor de texto plano) — asi el log completo de una corrida queda
persistido junto al resto de los artefactos de salida (subtitulos,
pipeline_timings.json, etc.), no solo visible mientras el proceso corre.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import IO

import structlog
from structlog.types import EventDict, Processor, WrappedLogger


class _DualRenderer:
    """Ultimo processor de la cadena: renderiza el evento DOS VECES (con
    color para la consola, en texto plano para el archivo) y escribe ambas
    copias directamente, en vez de dejar que structlog imprima una sola
    salida generica. Termina la cadena con ``DropEvent`` para que ningun
    processor/logger posterior vuelva a imprimir lo mismo.
    """

    def __init__(self, console_stream: IO[str], file_stream: IO[str] | None, json_logs: bool) -> None:
        self._console_stream = console_stream
        self._file_stream = file_stream
        self._console_renderer: Processor
        self._file_renderer: Processor
        if json_logs:
            self._console_renderer = structlog.processors.JSONRenderer()
            self._file_renderer = structlog.processors.JSONRenderer()
        else:
            self._console_renderer = structlog.dev.ConsoleRenderer(colors=True)
            self._file_renderer = structlog.dev.ConsoleRenderer(colors=False)

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> None:
        console_line = self._console_renderer(logger, method_name, dict(event_dict))
        self._console_stream.write(str(console_line) + "\n")
        self._console_stream.flush()

        if self._file_stream is not None:
            file_line = self._file_renderer(logger, method_name, dict(event_dict))
            self._file_stream.write(str(file_line) + "\n")
            self._file_stream.flush()

        raise structlog.DropEvent


def configure_logging(level: str = "INFO", json_logs: bool = False, log_file: Path | None = None) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )

    file_handle: IO[str] | None = None
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Deliberadamente sin "with": este handle debe seguir abierto durante
        # TODA la corrida (se escribe una linea por cada evento de log), no
        # solo dentro de esta funcion de configuracion. Lo cierra el SO al
        # terminar el proceso.
        file_handle = open(log_file, "w", encoding="utf-8")  # noqa: SIM115

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _DualRenderer(console_stream=sys.stdout, file_stream=file_handle, json_logs=json_logs),
    ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        # _DualRenderer ya escribio todo y corta la cadena con DropEvent;
        # este logger nunca llega a ejecutarse, pero structlog igual
        # requiere una factory valida.
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
