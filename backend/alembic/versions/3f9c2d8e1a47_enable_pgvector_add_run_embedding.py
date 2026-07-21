"""enable pgvector, add run embedding columns

Revision ID: 3f9c2d8e1a47
Revises: 2d5b7184ce46
Create Date: 2026-07-21 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '3f9c2d8e1a47'
down_revision: Union[str, Sequence[str], None] = '2d5b7184ce46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # 384 dims = all-MiniLM-L6-v2 output size (see app/services/ask.py)
    op.add_column("runs", sa.Column("embedding", Vector(384), nullable=True))
    op.add_column("runs", sa.Column("embedding_text_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("runs", "embedding_text_hash")
    op.drop_column("runs", "embedding")
    # The extension is left installed — dropping it would be destructive if
    # anything else ever comes to depend on it, and it's harmless when unused.
