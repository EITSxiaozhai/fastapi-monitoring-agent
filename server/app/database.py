"""数据库连接与初始化。

使用 SQLAlchemy 2.0 async + asyncpg 连接 TimescaleDB。
监控指标本质是时序数据，`metrics` 表会被转换为 TimescaleDB hypertable，
按时间自动分区，从而获得高写入吞吐与高效的时间范围查询。
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import get_settings
from .models import Base

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def session_dependency() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖注入用的会话生成器。"""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """建表并配置 TimescaleDB hypertable / 保留策略。

    对普通 PostgreSQL 也能工作（自动跳过 timescaledb 专有语句）。
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # 轻量级自动迁移：为已存在的旧表补充新增列（幂等）。
        migrations = [
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS public_ip VARCHAR(64) DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS country_code VARCHAR(8) DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS country VARCHAR(64) DEFAULT ''",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS disk_total BIGINT DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS disk_used BIGINT DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS disk_percent DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS net_sent_rate DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS net_recv_rate DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS net_bytes_sent BIGINT DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS net_bytes_recv BIGINT DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS tcp_connections INTEGER DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS tcp_established INTEGER DEFAULT 0",
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS top_processes JSON",
            "ALTER TABLE metrics ADD COLUMN IF NOT EXISTS disk_percent DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE metrics ADD COLUMN IF NOT EXISTS net_sent_rate DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE metrics ADD COLUMN IF NOT EXISTS net_recv_rate DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE metrics ADD COLUMN IF NOT EXISTS tcp_connections INTEGER DEFAULT 0",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception:  # noqa: BLE001 - 非 PostgreSQL 或已存在时忽略
                pass

        # 尝试启用 TimescaleDB 扩展并转换 hypertable。
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE"))
            await conn.execute(
                text(
                    "SELECT create_hypertable('metrics', 'time', "
                    "if_not_exists => TRUE, migrate_data => TRUE)"
                )
            )
            retention = get_settings().retention_days
            await conn.execute(
                text(
                    "SELECT add_retention_policy('metrics', "
                    f"INTERVAL '{retention} days', if_not_exists => TRUE)"
                )
            )
        except Exception:  # noqa: BLE001 - 非 TimescaleDB 环境下降级为普通表
            pass


async def dispose_db() -> None:
    await engine.dispose()
