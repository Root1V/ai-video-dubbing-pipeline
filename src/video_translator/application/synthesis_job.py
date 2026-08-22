"""DTO de una tarea de sintesis de voz: lo que hace falta para generar un
clip de audio y donde colocarlo despues en la mezcla final.

Vive en la capa de aplicacion (no es un concepto de dominio ni de
infraestructura): es el contrato entre ``TranslateVideoUseCase`` (que decide
QUE sintetizar y CUANDO debe sonar) y el motor de sintesis concreto (que solo
sabe COMO generar audio). Al construir la lista completa de tareas antes de
ejecutar ninguna, el caso de uso puede despacharlas de forma secuencial o en
paralelo (ver ``BatchSpeechSynthesizer``) sin cambiar su propia logica.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SynthesisJob:
    output_path: Path
    text: str
    target_duration_seconds: float
    speaker_reference_wav: Path | None
    language: str
    # Los siguientes dos campos no los usa el motor de TTS al generar el
    # audio; se transportan junto a la tarea para que, una vez completada
    # (en cualquier orden, si se ejecuto en paralelo), el caso de uso pueda
    # reconstruir la lista de mezcla (start, path, hueco_disponible) sin
    # tener que mantener una estructura separada en paralelo.
    start_seconds: float
    max_duration_seconds: float
