# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

WORKDIR /app

# 先复制依赖清单以利用构建缓存
COPY pyproject.toml uv.lock* ./
COPY server/pyproject.toml server/pyproject.toml
COPY agent/pyproject.toml agent/pyproject.toml

# 仅安装 server 及其依赖到独立虚拟环境
COPY server/ server/
RUN uv venv /opt/venv \
    && VIRTUAL_ENV=/opt/venv uv pip install --python /opt/venv/bin/python ./server

# ---------- runtime ----------
FROM python:3.12-slim-bookworm AS runtime

# 创建非 root 用户，权限最小化
RUN groupadd --system app && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app server/app /app/app

WORKDIR /app
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
