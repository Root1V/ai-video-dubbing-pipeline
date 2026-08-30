"""Router del catalogo de musica de fondo (RM-26): listado (cualquier usuario
autenticado, para elegir pista al crear un micro-video) y alta/baja (solo
admin, panel de mantenimiento)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from video_translator.config import load_settings
from video_translator.container import build_music_track_media_processor
from video_translator.web.config import WebSettings
from video_translator.web.db.models import MusicCategory, MusicTrack, User
from video_translator.web.deps import get_current_user, get_db_session, require_admin
from video_translator.web.routers.projects import get_web_settings
from video_translator.web.schemas.music import MusicTrackListOut, MusicTrackOut
from video_translator.web.services.music_tracks import add_music_track, delete_music_track

router = APIRouter(prefix="/music-tracks", tags=["music-tracks"])


def _parse_category(category: str) -> MusicCategory:
    try:
        return MusicCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Categoria invalida: {category}",
        ) from None


@router.get("", response_model=MusicTrackListOut)
def list_music_tracks(
    # str, no MusicCategory: un Literal/Enum como tipo de un Query() rompe la
    # deteccion de "parametro FastAPI" que ruff usa para no marcar B008 en el
    # Query(...) del default -- se valida a mano en _parse_category.
    category: str | None = Query(None),
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> MusicTrackListOut:
    stmt = select(MusicTrack).order_by(MusicTrack.created_at.desc())
    if category is not None:
        stmt = stmt.where(MusicTrack.category == _parse_category(category))
    items = list(db.execute(stmt).scalars().all())
    return MusicTrackListOut(items=[MusicTrackOut.model_validate(t) for t in items])


@router.post("", response_model=MusicTrackOut, status_code=status.HTTP_201_CREATED)
def create_music_track(
    title: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session),
    settings: WebSettings = Depends(get_web_settings),
) -> MusicTrackOut:
    media_processor = build_music_track_media_processor(load_settings())
    track = add_music_track(
        file=file,
        title=title,
        category=_parse_category(category),
        settings=settings,
        media_processor=media_processor,
        db=db,
    )
    return MusicTrackOut.model_validate(track)


@router.delete("/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_music_track_endpoint(
    track_id: uuid.UUID,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db_session),
) -> None:
    track = db.get(MusicTrack, track_id)
    if track is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pista no encontrada.")
    delete_music_track(track, db)
