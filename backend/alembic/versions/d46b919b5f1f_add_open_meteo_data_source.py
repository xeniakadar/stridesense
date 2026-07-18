"""add open_meteo data source

Revision ID: d46b919b5f1f
Revises: f96e8b0bf478
Create Date: 2026-07-18 13:42:48.070590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd46b919b5f1f'
down_revision: Union[str, Sequence[str], None] = 'f96e8b0bf478'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE data_source ADD VALUE IF NOT EXISTS 'OPEN_METEO'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres cannot remove a value from an enum type; leaving it is harmless.
    pass
