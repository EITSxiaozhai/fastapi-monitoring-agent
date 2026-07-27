"""add_user_machines_display_prefs

Revision ID: db7763314aba
Revises:
Create Date: 2026-07-27 14:49:35.986900

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'db7763314aba'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_not_exists(table: str, column: str, col_type: str) -> None:
    op.execute(
        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}"
    )


def _set_not_null(table: str, column: str, backfill_sql: str | None = None) -> None:
    """仅在列当前允许 NULL 时回填并设为 NOT NULL。"""
    if backfill_sql:
        op.execute(backfill_sql)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = '{table}'
                  AND column_name = '{column}'
                  AND is_nullable = 'YES'
            ) THEN
                EXECUTE 'ALTER TABLE {table} ALTER COLUMN {column} SET NOT NULL';
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    """兼容已由 init_db/create_all 建好的旧库。"""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_machines_display_prefs (
            user_id VARCHAR(128) NOT NULL PRIMARY KEY,
            show_stat_cards BOOLEAN NOT NULL DEFAULT true,
            show_machine_cards BOOLEAN NOT NULL DEFAULT true
        )
        """
    )

    for col, col_type in (
        ('net_errin', 'BIGINT DEFAULT 0'),
        ('net_errout', 'BIGINT DEFAULT 0'),
        ('net_dropin', 'BIGINT DEFAULT 0'),
        ('net_dropout', 'BIGINT DEFAULT 0'),
        ('net_errin_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('net_errout_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('net_dropin_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('net_dropout_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('tcp_retrans', 'BIGINT DEFAULT 0'),
        ('tcp_retrans_rate', 'DOUBLE PRECISION DEFAULT 0'),
    ):
        _add_column_if_not_exists('agents', col, col_type)

    for col, backfill in (
        ('public_ip', "UPDATE agents SET public_ip = '' WHERE public_ip IS NULL"),
        ('country_code', "UPDATE agents SET country_code = '' WHERE country_code IS NULL"),
        ('country', "UPDATE agents SET country = '' WHERE country IS NULL"),
        ('disk_total', 'UPDATE agents SET disk_total = 0 WHERE disk_total IS NULL'),
        ('disk_used', 'UPDATE agents SET disk_used = 0 WHERE disk_used IS NULL'),
        ('disk_percent', 'UPDATE agents SET disk_percent = 0 WHERE disk_percent IS NULL'),
        ('net_sent_rate', 'UPDATE agents SET net_sent_rate = 0 WHERE net_sent_rate IS NULL'),
        ('net_recv_rate', 'UPDATE agents SET net_recv_rate = 0 WHERE net_recv_rate IS NULL'),
        ('net_bytes_sent', 'UPDATE agents SET net_bytes_sent = 0 WHERE net_bytes_sent IS NULL'),
        ('net_bytes_recv', 'UPDATE agents SET net_bytes_recv = 0 WHERE net_bytes_recv IS NULL'),
        ('tcp_connections', 'UPDATE agents SET tcp_connections = 0 WHERE tcp_connections IS NULL'),
        ('tcp_established', 'UPDATE agents SET tcp_established = 0 WHERE tcp_established IS NULL'),
    ):
        _set_not_null('agents', col, backfill)

    op.execute("UPDATE agents SET top_processes = '[]'::json WHERE top_processes IS NULL")
    _set_not_null('agents', 'top_processes')
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_attrdef d
                JOIN pg_attribute a ON a.attrelid = d.adrelid AND a.attnum = d.adnum
                JOIN pg_class c ON c.oid = a.attrelid
                WHERE c.relname = 'agents' AND a.attname = 'top_processes'
            ) THEN
                ALTER TABLE agents ALTER COLUMN top_processes SET DEFAULT '[]'::json;
            END IF;
        END $$;
        """
    )

    for col, col_type in (
        ('net_errin_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('net_errout_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('net_dropin_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('net_dropout_rate', 'DOUBLE PRECISION DEFAULT 0'),
        ('tcp_retrans_rate', 'DOUBLE PRECISION DEFAULT 0'),
    ):
        _add_column_if_not_exists('metrics', col, col_type)

    for col, backfill in (
        ('disk_percent', 'UPDATE metrics SET disk_percent = 0 WHERE disk_percent IS NULL'),
        ('net_sent_rate', 'UPDATE metrics SET net_sent_rate = 0 WHERE net_sent_rate IS NULL'),
        ('net_recv_rate', 'UPDATE metrics SET net_recv_rate = 0 WHERE net_recv_rate IS NULL'),
        ('tcp_connections', 'UPDATE metrics SET tcp_connections = 0 WHERE tcp_connections IS NULL'),
    ):
        _set_not_null('metrics', col, backfill)


def downgrade() -> None:
  op.drop_table('user_machines_display_prefs')
