"""Add schedule_display_order to User model

Revision ID: 16585a9dda8f
Revises: d9fa48b7359c
Create Date: 2025-05-08 16:19:48.926538

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16585a9dda8f'
down_revision = 'd9fa48b7359c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('schedule_display_order', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_user_schedule_display_order'), ['schedule_display_order'], unique=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_schedule_display_order'))
        batch_op.drop_column('schedule_display_order')

    # ### end Alembic commands ###
