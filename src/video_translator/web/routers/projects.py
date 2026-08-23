"""Router de proyectos: creacion (upload multipart), listado, detalle, status, borrado."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path as FsPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from video_translator.web.config import WebSettings, load_web_settings
from video_translator.web.db.models import Project, ProjectStatus, User
from video_translator.web.deps import get_current_user, get_db_session
from video_translator.web.schemas.projects import ProjectListOut, ProjectOut, ProjectStatusOut
from video_translator.web.services import storage
from video_translator.web.services.status_reader import read_project_status
from video_translator.web.tasks.run_project import run_stub_project

router = APIRouter(prefix="/projects", tags=["projects"])


def get_web_settings() -> WebSettings:
    return load_web_settings()


def _get_owned_project(project_id: uuid.UUID, user: User, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado.")
    return project


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    name: str = Form(...),
    service_type: str = Form(...),
    output_mode: str = Form(...),
    file: UploadFile = File(...),
    context_prompt: str = Form(""),
    tone: str | None = Form(None),
    glossary: str = Form("{}"),
    source_lang: str = Form("en"),
    target_lang: str = Form("es"),
    diarize: bool = Form(False),
    min_speakers: int | None = Form(None),
    max_speakers: int | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
    settings: WebSettings = Depends(get_web_settings),
) -> Project:
    try:
        glossary_dict = json.loads(glossary)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="glossary no es JSON valido."
        ) from exc
    if not isinstance(glossary_dict, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="glossary debe ser un objeto JSON.",
        )

    project_id = uuid.uuid4()
    config = {
        "context_prompt": context_prompt,
        "tone": tone,
        "glossary": glossary_dict,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "diarize": diarize,
        "min_speakers": min_speakers,
        "max_speakers": max_speakers,
    }

    project = Project(
        id=project_id,
        user_id=current_user.id,
        name=name,
        service_type=service_type,
        source_type="upload",
        input_video_path="",  # se completa abajo tras guardar el archivo
        output_dir=str(storage.output_dir_for(project_id, settings)),
        output_mode=output_mode,
        config=config,
        status=ProjectStatus.QUEUED,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    saved_path = storage.save_upload(file, project.id, settings)
    project.input_video_path = str(saved_path)
    db.commit()

    task = run_stub_project.delay(str(project.id))
    project.celery_task_id = task.id
    db.commit()
    db.refresh(project)

    return project


@router.get("", response_model=ProjectListOut)
def list_projects(
    status_filter: str | None = Query(None, alias="status"),
    service_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ProjectListOut:
    stmt = select(Project).where(Project.user_id == current_user.id)
    if status_filter is not None:
        stmt = stmt.where(Project.status == status_filter)
    if service_type is not None:
        stmt = stmt.where(Project.service_type == service_type)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    stmt = stmt.order_by(Project.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.execute(stmt).scalars().all())

    return ProjectListOut(
        items=[ProjectOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> Project:
    return _get_owned_project(project_id, current_user, db)


@router.get("/{project_id}/status", response_model=ProjectStatusOut)
def get_project_status(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> ProjectStatusOut:
    project = _get_owned_project(project_id, current_user, db)
    return ProjectStatusOut(**read_project_status(project))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> None:
    project = _get_owned_project(project_id, current_user, db)

    # input_video_path vive en su propia carpeta por proyecto
    # (STORAGE_ROOT/uploads/{project_id}/...) -- se borra la carpeta entera,
    # no solo el archivo, para no dejar directorios vacios huerfanos.
    upload_dir = FsPath(project.input_video_path).parent if project.input_video_path else None
    for path_str_or_path in (upload_dir, project.output_dir):
        if not path_str_or_path:
            continue
        try:
            path = FsPath(path_str_or_path)
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
        except OSError:
            pass

    db.delete(project)
    db.commit()
