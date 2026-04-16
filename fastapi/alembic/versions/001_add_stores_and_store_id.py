"""add stores table and store_id to all tables

Revision ID: 001
Revises:
Create Date: 2026-03-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Create stores table (if not already created by auto-create)
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS stores (
            id SERIAL PRIMARY KEY,
            owner_email VARCHAR(200) NOT NULL UNIQUE,
            name VARCHAR(200),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            is_active BOOLEAN DEFAULT true
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_stores_owner_email ON stores (owner_email)"
    ))

    # 2. Insert debug store so existing data can be linked
    conn.execute(sa.text(
        "INSERT INTO stores (owner_email, name) "
        "VALUES ('debug@localhost', 'Debug Store') "
        "ON CONFLICT (owner_email) DO NOTHING"
    ))

    # 3. Add store_id + is_registered to auth_users
    conn.execute(sa.text(
        "ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS "
        "store_id INTEGER REFERENCES stores(id)"
    ))
    conn.execute(sa.text(
        "ALTER TABLE auth_users ADD COLUMN IF NOT EXISTS "
        "is_registered BOOLEAN DEFAULT false"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_auth_users_store_id ON auth_users (store_id)"
    ))

    # 4. Add store_id to every tenant-scoped table
    tables = [
        "restaurant_settings", "staff", "categories", "menu_items",
        "tables", "customers", "cart_items", "orders", "order_items",
        "daily_item_performance", "daily_business_stats",
    ]
    for table_name in tables:
        conn.execute(sa.text(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS "
            f"store_id INTEGER REFERENCES stores(id)"
        ))
        conn.execute(sa.text(
            f"CREATE INDEX IF NOT EXISTS ix_{table_name}_store_id "
            f"ON {table_name} (store_id)"
        ))

    # 5. Backfill: point all existing rows to the debug store
    all_tables = ["auth_users"] + tables
    for table_name in all_tables:
        conn.execute(sa.text(
            f"UPDATE {table_name} SET store_id = "
            f"(SELECT id FROM stores WHERE owner_email = 'debug@localhost') "
            f"WHERE store_id IS NULL"
        ))


def downgrade() -> None:
    conn = op.get_bind()

    tables = [
        "daily_business_stats", "daily_item_performance", "order_items",
        "orders", "cart_items", "customers", "tables", "menu_items",
        "categories", "staff", "restaurant_settings",
    ]
    for table_name in tables:
        conn.execute(sa.text(f"DROP INDEX IF EXISTS ix_{table_name}_store_id"))
        conn.execute(sa.text(
            f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS store_id"
        ))

    conn.execute(sa.text("DROP INDEX IF EXISTS ix_auth_users_store_id"))
    conn.execute(sa.text("ALTER TABLE auth_users DROP COLUMN IF EXISTS is_registered"))
    conn.execute(sa.text("ALTER TABLE auth_users DROP COLUMN IF EXISTS store_id"))

    conn.execute(sa.text("DROP INDEX IF EXISTS ix_stores_owner_email"))
    conn.execute(sa.text("DROP TABLE IF EXISTS stores"))
