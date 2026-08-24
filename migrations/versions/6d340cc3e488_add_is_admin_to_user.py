"""Add is_admin to User

Revision ID: 6d340cc3e488
Revises:
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa


revision = "6d340cc3e488"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false()
        )
    )


def downgrade():
    op.drop_column("user", "is_admin")