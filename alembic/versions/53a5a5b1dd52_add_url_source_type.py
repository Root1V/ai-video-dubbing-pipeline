"""add_url_source_type

Revision ID: 53a5a5b1dd52
Revises: 7f111e74e5cb
Create Date: 2026-08-24 15:02:29.027087

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '53a5a5b1dd52'
down_revision: str | Sequence[str] | None = '7f111e74e5cb'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE sourcetype ADD VALUE IF NOT EXISTS 'url'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres no soporta ALTER TYPE ... DROP VALUE: revertir requeriria
    # recrear el tipo enum entero y remapear la columna, arriesgando cualquier
    # fila 'url' ya existente. Se deja como no-op deliberado (mismo criterio
    # que 27d6738db030_add_tts_service_type.py).
