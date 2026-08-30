"""Alta/baja del catalogo de musica de fondo (RM-26): guarda el archivo
subido, lo limpia (recorta silencio inicial, convierte a WAV via
`MediaProcessor.clean_music_track`) y crea/borra la fila en BD."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from video_translator.application.interfaces import MediaProcessor
from video_translator.web.config import WebSettings
from video_translator.web.db.models import MusicCategory, MusicTrack


def _save_upload_to_tmp(file: UploadFile, settings: WebSettings) -> Path:
    tmp_dir = Path(settings.storage_root) / "tmp" / "music_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    destination = tmp_dir / f"{uuid.uuid4()}_{file.filename}"
    with destination.open("wb") as out_file:
        shutil.copyfileobj(file.file, out_file)
    return destination


def add_music_track(
    file: UploadFile,
    title: str,
    category: MusicCategory,
    settings: WebSettings,
    media_processor: MediaProcessor,
    db: Session,
) -> MusicTrack:
    track_id = uuid.uuid4()
    tmp_path = _save_upload_to_tmp(file, settings)
    try:
        final_path = Path(settings.storage_root) / "music" / f"{track_id}.wav"
        media_processor.clean_music_track(tmp_path, final_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    track = MusicTrack(id=track_id, title=title, category=category, file_path=str(final_path))
    db.add(track)
    db.commit()
    db.refresh(track)
    return track


def delete_music_track(track: MusicTrack, db: Session) -> None:
    Path(track.file_path).unlink(missing_ok=True)
    db.delete(track)
    db.commit()
