"""Manejo de archivos subidos y directorios de salida en STORAGE_ROOT."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile

from video_translator.web.config import WebSettings


def save_upload(file: UploadFile, project_id: UUID, settings: WebSettings) -> Path:
    """Guarda el archivo subido en STORAGE_ROOT/uploads/{project_id}/{filename},
    escribiendo en streaming (sin cargar el archivo completo en memoria)."""
    upload_dir = Path(settings.storage_root) / "uploads" / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / str(file.filename)
    with destination.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)
    return destination


def output_dir_for(project_id: UUID, settings: WebSettings) -> Path:
    """Ruta del directorio de salida del proyecto (no se crea aca; el paso M2
    que llame al pipeline real la creara, igual que hace cli.py)."""
    return Path(settings.storage_root) / "outputs" / str(project_id)


def save_text(text: str, project_id: UUID, settings: WebSettings) -> Path:
    """Guarda texto (p.ej. el contenido a sintetizar del servicio TTS) en
    STORAGE_ROOT/uploads/{project_id}/input.txt, mismo directorio que
    `save_upload` -- asi `input_video_path` sigue siendo el "archivo de
    entrada" del proyecto incluso cuando ese servicio no sube ningun archivo."""
    upload_dir = Path(settings.storage_root) / "uploads" / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    destination = upload_dir / "input.txt"
    destination.write_text(text, encoding="utf-8")
    return destination
