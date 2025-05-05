"""Add discount_percentage column properly

Revision ID: new2
Revises:
Create Date: 2025-05-05 15:32:43.043273

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = "new2"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Use direct SQL to add the column
    op.execute(
        text(
            "ALTER TABLE appointment ADD COLUMN discount_percentage NUMERIC(5,2) NOT NULL DEFAULT 0.0"
        )
    )


def downgrade():
    # Use direct SQL to drop the column
    op.execute(text("ALTER TABLE appointment DROP COLUMN discount_percentage"))
