"""add_music_tracks

Revision ID: a1b2c3d4e5f6
Revises: 5e30245e22ef
Create Date: 2026-08-30 00:00:00.000000

"""
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '5e30245e22ef'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Las 4 pistas CC0 de RM-24 ya vivian como un dict fijo en container.py
# (BACKGROUND_MUSIC_TRACKS); al pasar el catalogo a la BD (RM-26) se
# migran ahora como filas, cada una asignada a una de las 5 categorias
# nuevas, sin reprocesarlas (ya son CC0 limpias, ver assets/background_music/SOURCES.md).
_ASSETS_DIR = Path(__file__).resolve().parents[2] / "src" / "video_translator" / "assets" / "background_music"

_SEED_TRACKS = [
    ("Backbeat", "energy_pop", "backbeat.mp3"),
    ("Elevate Inspirate", "commercials_professional", "elevate_inspirate.mp3"),
    ("Forest Frolic Loop", "calm_meditation", "forest_frolic_loop.mp3"),
    ("Think About It", "commercials_professional", "think_about_it.mp3"),
]


def upgrade() -> None:
    op.create_table(
        'music_tracks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('file_path', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    music_tracks_table = sa.table(
        'music_tracks',
        sa.column('id', sa.Uuid()),
        sa.column('title', sa.String()),
        sa.column('category', sa.String()),
        sa.column('file_path', sa.String()),
        sa.column('created_at', sa.DateTime()),
    )
    op.bulk_insert(
        music_tracks_table,
        [
            {
                'id': uuid.uuid4(),
                'title': title,
                'category': category,
                'file_path': str(_ASSETS_DIR / filename),
                'created_at': datetime.now(timezone.utc),
            }
            for title, category, filename in _SEED_TRACKS
        ],
    )


def downgrade() -> None:
    op.drop_table('music_tracks')
