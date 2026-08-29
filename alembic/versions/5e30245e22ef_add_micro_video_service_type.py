"""add_micro_video_service_type

Revision ID: 5e30245e22ef
Revises: 53a5a5b1dd52
Create Date: 2026-08-29 15:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '5e30245e22ef'
down_revision: str | Sequence[str] | None = '53a5a5b1dd52'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE servicetype ADD VALUE IF NOT EXISTS 'micro_video'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres no soporta ALTER TYPE ... DROP VALUE: revertir requeriria
    # recrear el tipo enum entero y remapear la columna, arriesgando cualquier
    # fila 'micro_video' ya existente. Se deja como no-op deliberado (mismo
    # patron que 27d6738db030_add_tts_service_type.py).
