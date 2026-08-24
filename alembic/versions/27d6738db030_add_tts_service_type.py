"""add_tts_service_type

Revision ID: 27d6738db030
Revises: cae0ae9ef1c7
Create Date: 2026-08-23 20:05:40.478599

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '27d6738db030'
down_revision: str | Sequence[str] | None = 'cae0ae9ef1c7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE servicetype ADD VALUE IF NOT EXISTS 'tts'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres no soporta ALTER TYPE ... DROP VALUE: revertir requeriria
    # recrear el tipo enum entero y remapear la columna, arriesgando cualquier
    # fila 'tts' ya existente. Se deja como no-op deliberado (ver
    # migraciones similares en otros proyectos con el mismo patron aditivo).
