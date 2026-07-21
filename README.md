# fastapi-mon · 机器监控系统

一个前后端分离的机器监控系统，由三部分组成：

- **管理端 / 后端 (`server/`)**：FastAPI + TimescaleDB。通过 **WebSocket** 接收客户端上报的指标，提供 **JWT 登录**、REST 查询接口，以及面向前端的 **WebSocket 实时推送**。
- **前端 (`ant-design-pro-master/`)**：官方 **Ant Design Pro (UmiJS Max)**。带登录模块，用**图表**实时展示每台机器的 CPU、内存、内核、进程数、负载、在线状态等。
- **客户端 / Agent (`agent/`)**：Python + `psutil`，通过 **WebSocket** 周期上报本机指标。为容器化设计，运行时**权限最小化**。

依赖用 **uv**（后端/客户端，monorepo workspace）与 **npm**（前端）管理；数据库为 **TimescaleDB**（PostgreSQL 时序扩展），指标表为 hypertable 自动按时间分区。

---

## 架构

```
                    WebSocket 上报 (/ws/ingest, X-API-Key)
┌─────────────┐    ─────────────────────────────────▶   ┌──────────────┐
│  客户端 Agent │                                          │   管理端后端   │──▶ TimescaleDB
│  (psutil)    │  ◀───── 确认 ─────                        │  (FastAPI)   │    (hypertable)
└─────────────┘                                          │              │
                                                         │  JWT 登录     │
┌─────────────────────┐   REST 登录/历史 (JWT)            │  REST 查询    │
│  前端 Ant Design Pro │ ◀──────────────────────────────▶ │  WS 实时推送   │
│  (图表 + 登录)        │   WebSocket 实时订阅 (/ws/dashboard)│              │
└─────────────────────┘ ◀──────────────────────────────  └──────────────┘
```

采集指标：`os` / `kernel` / `arch` / `cpu_count` / `cpu_percent` / `mem_total` / `mem_used` / `mem_percent` / `process_count` / `load1` / `uptime` / `磁盘` / `网络 IO` / `TCP 连接` / `Top 进程` / `外网 IP + 国家`（卡片右上角显示国旗）。

---

## 方式一：Docker Compose 一键启动（推荐）

会启动 TimescaleDB、后端、前端(Nginx)，以及一个监控**宿主机**的示例客户端。

```bash
cp .env.example .env      # 按需修改 API_KEY / ADMIN_PASSWORD / JWT_SECRET
docker compose up --build
```

- 前端： http://localhost:8080 （默认账号见 `.env`：`admin / admin123`）
- 后端 API 文档： http://localhost:8000/docs

> 示例客户端通过只读挂载宿主机 `/proc`（`HOST_PROC=/host/proc`）采集**宿主机**数据，
> 同时容器保持 `cap_drop: ALL` + `no-new-privileges` + `read_only` 的最小权限。

---

## 方式二：本地开发

后端默认端口 **8000**，前端 dev server 端口 **8001**（前端通过 dev proxy 把 `/api`、`/ws` 转发到后端）。

```bash
# 1) 启动 TimescaleDB（或任意 PostgreSQL）
docker run -d --name mon-db -p 5432:5432 \
  -e POSTGRES_USER=mon -e POSTGRES_PASSWORD=mon -e POSTGRES_DB=mon \
  timescale/timescaledb:latest-pg16

# 2) 后端：安装依赖并启动（端口 8000）
uv sync --all-packages
uv run uvicorn app.main:app --reload --app-dir server --port 8000

# 3) 客户端：另开终端，采集本机并通过 WS 上报
$env:SERVER_URL="ws://localhost:8000"; $env:API_KEY="changeme-dev-key"
uv run mon-agent

# 4) 前端：进入脚手架目录，安装并启动（端口 8001）
cd ant-design-pro-master/ant-design-pro-master
npm install
npm run dev
```

访问 http://localhost:8001 ，用 `admin / admin123` 登录。

> 未检测到 TimescaleDB 扩展时，后端会自动降级为普通 PostgreSQL 表，功能不受影响。

---

## 配置

### 后端（环境变量前缀 `MON_`）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `MON_DATABASE_URL` | `postgresql+asyncpg://mon:mon@localhost:5432/mon` | 数据库连接串 |
| `MON_API_KEYS` | `changeme-dev-key` | 客户端上报允许的 API Key，多个逗号分隔 |
| `MON_OFFLINE_THRESHOLD_SECONDS` | `60` | 超过该秒数未上报判定为离线 |
| `MON_RETENTION_DAYS` | `30` | 历史指标保留天数 |
| `MON_ADMIN_USERNAME` | `admin` | 前端登录用户名 |
| `MON_ADMIN_PASSWORD` | `admin123` | 前端登录密码 |
| `MON_JWT_SECRET` | `change-me-...` | JWT 签名密钥（生产务必修改） |
| `MON_JWT_EXPIRE_MINUTES` | `1440` | 令牌有效期（分钟） |
| `MON_BROADCAST_INTERVAL_SECONDS` | `5` | 服务端向前端广播全量快照的间隔 |

### 客户端（环境变量）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SERVER_URL` | `ws://localhost:8000` | 管理端地址（支持 `http(s)`/`ws(s)`，自动转换） |
| `API_KEY` | `changeme-dev-key` | 上报鉴权 Key，需与后端一致 |
| `INTERVAL` | `2` | 上报间隔（秒） |
| `AGENT_ID` | 自动 | 机器唯一标识，默认取 `/etc/machine-id` 或主机名派生 |
| `AGENT_HOSTNAME` | 主机名 | 展示用主机名 |
| `HOST_PROC` | 空 | 指向只读挂载的宿主机 `/proc`，用于采集宿主机而非容器数据 |
| `DISK_PATH` | `/`（Win 为 `C:\`） | 磁盘使用率统计路径，可指向只读挂载的宿主机目录 |
| `TOP_N` | `5` | 上报 CPU 占用最高的进程数量 |
| `GEOIP_DISABLE` | 空 | 置 `1` 关闭外网 IP / 国家查询 |
| `GEOIP_TTL` | `1800` | 外网 IP / 国家缓存有效期（秒） |
| `GEOIP_ENDPOINT` | `ip-api.com` | 查询接口（需返回 `query`/`countryCode`/`country`） |

---

## 客户端权限最小化

- **distroless 基础镜像**：无 shell、无包管理器，攻击面极小
- **非 root 运行**：镜像默认 `nonroot` (uid 65532)
- **`cap_drop: ALL`**：丢弃所有 Linux capabilities
- **`no-new-privileges`**：禁止运行期提权
- **`read_only` 根文件系统**：容器文件系统只读
- **只读挂载 `/proc`**：需要宿主机数据时仅以只读方式挂载，不授予特权

---

## 接口一览

| 类型 | 路径 | 说明 |
| --- | --- | --- |
| WS | `/ws/ingest?api_key=` | 客户端上报（WebSocket） |
| WS | `/ws/dashboard?token=` | 前端实时订阅（需 JWT） |
| POST | `/api/v1/login/account` | 登录，返回 JWT |
| GET | `/api/v1/currentUser` | 当前用户（需 JWT） |
| POST | `/api/v1/login/outLogin` | 退出登录 |
| GET | `/api/v1/agents` | 所有机器 + 最新状态（需 JWT） |
| GET | `/api/v1/agents/{id}/metrics?minutes=60` | 单机历史指标（需 JWT） |
| GET | `/api/v1/summary` | 汇总统计（需 JWT） |
| GET | `/health` | 健康检查 |

---

## 项目结构

```
fastapi-mon/
├── docker-compose.yml
├── .env.example
├── server/                       # 后端(管理端)
│   ├── Dockerfile
│   └── app/
│       ├── main.py               # FastAPI 入口(CORS/路由/生命周期)
│       ├── config.py
│       ├── database.py           # TimescaleDB / hypertable
│       ├── models.py / schemas.py
│       ├── security.py           # JWT + API Key
│       ├── services.py           # 在线判定 / 快照构建
│       ├── realtime.py           # WebSocket 广播管理器
│       └── api/
│           ├── auth.py           # 登录 / currentUser
│           ├── dashboard.py      # REST 查询(需 JWT)
│           └── ws.py             # /ws/ingest + /ws/dashboard
├── agent/                        # 客户端
│   ├── Dockerfile                # distroless / 非 root
│   └── agent/
│       ├── main.py               # WebSocket 上报主循环 + 断线重连
│       ├── collector.py          # psutil 采集
│       └── config.py
└── ant-design-pro-master/        # 前端(Ant Design Pro)
    └── ant-design-pro-master/
        ├── Dockerfile.mon        # 生产镜像(Nginx)
        ├── nginx.mon.conf
        ├── config/               # 路由/代理(已适配)
        └── src/
            ├── services/mon.ts   # 机器监控 API + WS 订阅
            └── pages/machines/   # 机器监控页(图表 + 实时)
```
