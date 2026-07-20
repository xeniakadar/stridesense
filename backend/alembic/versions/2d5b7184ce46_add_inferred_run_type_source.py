"""add inferred run type source

Revision ID: 2d5b7184ce46
Revises: d46b919b5f1f
Create Date: 2026-07-20 16:30:52.597170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d5b7184ce46'
down_revision: Union[str, Sequence[str], None] = 'd46b919b5f1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE run_type_source ADD VALUE IF NOT EXISTS 'INFERRED'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres cannot remove a value from an enum type; leaving it is harmless.
    pass
