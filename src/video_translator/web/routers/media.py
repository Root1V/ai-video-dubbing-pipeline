"""Router de previsualizacion/busqueda de media externo (import por URL)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from video_translator.web.db.models import User
from video_translator.web.deps import get_current_user
from video_translator.web.schemas.media import MediaPreviewOut, MediaSearchOut
from video_translator.web.services.media_import import (
    InvalidUrlError,
    MediaImportError,
    fetch_preview,
    search_youtube,
)

router = APIRouter(prefix="/media", tags=["media"])


@router.get("/preview", response_model=MediaPreviewOut)
def preview(
    url: str = Query(...),
    _current_user: User = Depends(get_current_user),
) -> MediaPreviewOut:
    try:
        preview_data = fetch_preview(url)
    except InvalidUrlError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except MediaImportError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return MediaPreviewOut(**preview_data.__dict__)


@router.get("/search", response_model=MediaSearchOut)
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(12, ge=1, le=24),
    _current_user: User = Depends(get_current_user),
) -> MediaSearchOut:
    try:
        results = search_youtube(q, limit=limit)
    except MediaImportError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return MediaSearchOut(items=[MediaPreviewOut(**item.__dict__) for item in results])
