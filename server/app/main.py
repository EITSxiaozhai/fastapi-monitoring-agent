"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, dashboard, ws
from .config import get_settings
from .database import dispose_db, init_db
from .realtime import broadcaster


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    broadcaster.start()
    yield
    await broadcaster.stop()
    await dispose_db()


app = FastAPI(
    title="机器监控管理端",
    description="接收客户端 WebSocket 上报的机器指标（CPU / 内存 / 内核 / 进程数），"
    "提供 JWT 登录与实时数据推送。",
    version="0.2.0",
    lifespan=lifespan,
)

# 前端为独立 Ant Design Pro 项目，需允许跨域。来源通过 MON_CORS_ORIGINS 配置。
_origins = get_settings().cors_origin_list
_cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if _origins == ["*"]:
    # 通配 + 凭据不被浏览器接受，改用正则反射请求来源
    _cors_kwargs["allow_origin_regex"] = ".*"
else:
    _cors_kwargs["allow_origins"] = _origins
app.add_middleware(CORSMiddleware, **_cors_kwargs)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(ws.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok"}
