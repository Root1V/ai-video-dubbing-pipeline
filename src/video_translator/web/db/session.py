"""Engine y sessionmaker de SQLAlchemy. La creacion del engine es perezosa:
no conecta a la base de datos hasta que se use una sesion.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from video_translator.web.config import load_web_settings

_settings = load_web_settings()

engine = create_engine(_settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
