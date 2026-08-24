"""Add is_active to User"""

from alembic import op
import sqlalchemy as sa


revision = "44d246eb89f3"
down_revision = "6d340cc3e488"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true()
        )
    )


def downgrade():
    op.drop_column("user", "is_active")