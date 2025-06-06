"""Add Brand, Product and StockLevel models for inventory management

Revision ID: 1d436bddff8f
Revises: 65f9ff3f0dfd
Create Date: 2025-05-30 13:55:59.310600

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "1d436bddff8f"
down_revision = "65f9ff3f0dfd"
branch_labels = None
depends_on = None


def upgrade():
    # Тимчасово вимкнути перевірку зовнішніх ключів для SQLite
    bind = op.get_bind()
    if bind.engine.name == "sqlite":
        bind.execute(text("PRAGMA foreign_keys=OFF"))

    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "brand",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "product",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=50), nullable=False),
        sa.Column("volume_value", sa.Float(), nullable=True),
        sa.Column("volume_unit", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("min_stock_level", sa.Integer(), nullable=False),
        sa.Column("current_sale_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("last_cost_price", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brand.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )
    op.create_table(
        "stock_level",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id"),
    )
    with op.batch_alter_table("appointment", schema=None) as batch_op:
        batch_op.alter_column(
            "payment_status",
            existing_type=sa.VARCHAR(length=10),
            type_=sa.String(length=20),
            existing_nullable=False,
            existing_server_default=sa.text("'unpaid'"),
        )
        batch_op.alter_column(
            "payment_method",
            existing_type=sa.VARCHAR(length=50),
            type_=sa.Enum("CASH", "MALIBU", "FOP", "PRIVAT", "MONO", "DEBT", name="paymentmethod"),
            existing_nullable=True,
        )
        batch_op.drop_column("total_price")

    with op.batch_alter_table("service", schema=None) as batch_op:
        batch_op.alter_column(
            "base_price",
            existing_type=sa.REAL(),
            type_=sa.Float(),
            existing_nullable=True,
            existing_server_default=sa.text("(0.0)"),
        )

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column(
            "is_active_master", existing_type=sa.BOOLEAN(), nullable=False, existing_server_default=sa.text("0")
        )

    # ### end Alembic commands ###


def downgrade():
    # Тимчасово вимкнути перевірку зовнішніх ключів для SQLite
    bind = op.get_bind()
    if bind.engine.name == "sqlite":
        bind.execute(text("PRAGMA foreign_keys=OFF"))

    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.alter_column(
            "is_active_master", existing_type=sa.BOOLEAN(), nullable=True, existing_server_default=sa.text("0")
        )

    with op.batch_alter_table("service", schema=None) as batch_op:
        batch_op.alter_column(
            "base_price",
            existing_type=sa.Float(),
            type_=sa.REAL(),
            existing_nullable=True,
            existing_server_default=sa.text("(0.0)"),
        )

    with op.batch_alter_table("appointment", schema=None) as batch_op:
        batch_op.add_column(sa.Column("total_price", sa.REAL(), nullable=True))
        batch_op.alter_column(
            "payment_method",
            existing_type=sa.Enum("CASH", "MALIBU", "FOP", "PRIVAT", "MONO", "DEBT", name="paymentmethod"),
            type_=sa.VARCHAR(length=50),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "payment_status",
            existing_type=sa.String(length=20),
            type_=sa.VARCHAR(length=10),
            existing_nullable=False,
            existing_server_default=sa.text("'unpaid'"),
        )

    op.drop_table("stock_level")
    op.drop_table("product")
    op.drop_table("brand")
    # ### end Alembic commands ###
