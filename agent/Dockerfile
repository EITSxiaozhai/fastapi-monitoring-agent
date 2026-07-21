# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

WORKDIR /app

COPY agent/pyproject.toml ./pyproject.toml
COPY agent/ ./
RUN uv venv /opt/venv \
    && VIRTUAL_ENV=/opt/venv uv pip install --python /opt/venv/bin/python .

# ---------- runtime ----------
# distroless：无 shell、无包管理器，攻击面最小
FROM gcr.io/distroless/python3-debian12:nonroot AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/opt/venv/lib/python3.12/site-packages"

COPY --from=build /opt/venv /opt/venv
COPY --from=build /app/agent /app/agent

WORKDIR /app
# distroless:nonroot 默认以非 root (uid 65532) 运行
USER nonroot

ENTRYPOINT ["python", "-m", "agent.main"]
