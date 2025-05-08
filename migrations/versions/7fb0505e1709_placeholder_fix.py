"""empty message

Revision ID: 7fb0505e1709
Revises: d9fa48b7359c
Create Date: 2023-05-01 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7fb0505e1709"
down_revision = "d9fa48b7359c"  # Це правильно, виходячи з вашої історії
branch_labels = None
depends_on = None


def upgrade():
    pass  # Порожня функція, як і потрібно


def downgrade():
    pass  # Порожня функція, як і потрібно
