"""add_music_tracks

Revision ID: a1b2c3d4e5f6
Revises: 5e30245e22ef
Create Date: 2026-08-30 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '5e30245e22ef'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Nota: esta migracion originalmente tambien sembraba las 4 pistas CC0 de
# RM-24 (antes un dict fijo en container.py) como filas de ejemplo. Se
# quitó ese seed: esas pistas se reemplazaron por un catalogo real subido
# desde el panel de administracion (RM-26) y los .mp3 empaquetados que
# usaba el seed ya no estan en el repo -- una instalacion nueva arranca
# con el catalogo vacio, a la espera de que un admin suba pistas.


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


def downgrade() -> None:
    op.drop_table('music_tracks')
