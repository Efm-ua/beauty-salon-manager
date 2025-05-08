"""Merge placeholder 7fb0 and add_schedule_display_order 1658 branches

Revision ID: 65f9ff3f0dfd
Revises: 7fb0505e1709, 16585a9dda8f
Create Date: 2025-05-08 19:04:50.233164

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '65f9ff3f0dfd'
down_revision = ('7fb0505e1709', '16585a9dda8f')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
