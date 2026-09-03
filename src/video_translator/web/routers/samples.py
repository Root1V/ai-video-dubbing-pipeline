"""Router de muestras de audio empaquetadas con la app (voces publicas y
musica de fondo, ver container.py): sirve el archivo estatico para que la UI
pueda dejar escuchar un preview antes de elegir, sin depender de un proyecto."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from video_translator.container import (
    EMOJI_ASSETS_DIR,
    PUBLIC_VOICE_FEMALE_WAV,
    PUBLIC_VOICE_MALE_WAV,
)
from video_translator.web.db.models import MusicTrack, User
from video_translator.web.deps import get_current_user, get_db_session

router = APIRouter(prefix="/samples", tags=["samples"])

_PUBLIC_VOICES = {
    "public_female": PUBLIC_VOICE_FEMALE_WAV,
    "public_male": PUBLIC_VOICE_MALE_WAV,
}


@router.get("/voices/{voice_id}")
def get_voice_sample(
    voice_id: str,
    _current_user: User = Depends(get_current_user),
) -> FileResponse:
    file_path = _PUBLIC_VOICES.get(voice_id)
    if file_path is None or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voz no encontrada.")
    return FileResponse(path=file_path, filename=file_path.name)


@router.get("/music/{track_id}")
def get_music_sample(
    track_id: str,
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> FileResponse:
    try:
        track = db.get(MusicTrack, uuid.UUID(track_id))
    except ValueError:
        track = None
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pista no encontrada.")
    file_path = Path(track.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pista no encontrada.")
    return FileResponse(path=file_path, filename=file_path.name)


@router.get("/emoji/{emoji_id}")
def get_emoji_sample(
    emoji_id: str,
    _current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Sirve un PNG del set curado de emojis (ver RM-32) -- el editor los usa
    para el preview en el lienzo (arrastrar/soltar), la generacion real del
    video los resuelve por su cuenta (ver generate_micro_video.py)."""
    file_path = EMOJI_ASSETS_DIR / f"{emoji_id}.png"
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Emoji no encontrado.")
    return FileResponse(path=file_path, filename=file_path.name)
