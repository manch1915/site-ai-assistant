"""mark sample leads

Revision ID: b4136b4fe9ce
Revises: 913ed3b05f59
Create Date: 2026-10-19 22:14:03.142181
"""

from collections.abc import Sequence

import sqlalchemy as sa
import pgvector.sqlalchemy
from alembic import op

revision: str = "b4136b4fe9ce"
down_revision: str | None = "913ed3b05f59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads", sa.Column("sample", sa.Boolean(), server_default="false", nullable=False)
    )


def downgrade() -> None:
    op.drop_column("leads", "sample")
