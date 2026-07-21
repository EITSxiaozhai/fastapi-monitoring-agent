"""管理端配置。所有配置项均可通过环境变量覆盖。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MON_", env_file=".env", extra="ignore")

    # 数据库连接串 (SQLAlchemy async 格式)
    database_url: str = "postgresql+asyncpg://mon:mon@localhost:5432/mon"

    # 客户端上报使用的 API Key（多个用逗号分隔）
    api_keys: str = "changeme-dev-key"

    # 判定机器离线的阈值（秒）：超过该时间未上报视为离线
    offline_threshold_seconds: int = 60

    # 历史指标保留天数
    retention_days: int = 30

    # 管理端登录账号（JWT 认证）
    admin_username: str = "admin"
    admin_password: str = "admin123"
    jwt_secret: str = "change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # 服务端向前端广播实时快照的间隔（秒）
    broadcast_interval_seconds: float = 5.0

    # 允许跨域访问的前端来源（多个用逗号分隔）。
    # "*" 表示允许任意来源（开发便捷；此时会以正则反射来源以兼容携带凭据的请求）。
    # 生产建议显式配置，如：https://mon.example.com,https://admin.example.com
    cors_origins: str = "*"

    # Cloudflare Turnstile 人机验证
    # sitekey 为前端公开使用；secret 留空则后端不校验（便于本地开发）
    turnstile_sitekey: str = ""
    turnstile_secret: str = ""

    # 服务监听
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def api_key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
