# GitHub + Zeabur 部署说明

这套仓库适合在 Zeabur 里拆成 2 到 3 个服务：

- `frontend`：Next.js
- `backend`：FastAPI
- `postgres`：Zeabur 托管 PostgreSQL，可选

不建议直接把根目录的 `docker-compose.public.yml` 拿去给 Zeabur 用。Zeabur 官方文档明确说明目前不支持从 Docker Compose YAML 直接部署，因此这里应改为同仓库多服务部署。

## 推送到 GitHub 前

1. 先确认根目录 `.gitignore` 已生效，避免把 `.venv`、缓存、调试输出、数据库文件推上去。
2. 这个仓库当前没有现成远端仓库，推送前需要先创建 GitHub 仓库。
3. 如果你不希望公开代码，应创建 Private Repository。

## 推荐部署结构

### Demo 方案

如果你只是先把站点放到公网演示，不追求完整线上数据库，可以先只部署：

- `frontend`
- `backend`

当前仓库已经把 `backend/demo.db` 打进后端镜像里，并且当 `DATABASE_URL` 未配置时，会默认使用这个 SQLite 演示库。

也就是说，Zeabur 上即使暂时不创建 PostgreSQL，页面也可以先展示 demo 数据。

前端到后端的 `/api/v1/*` 请求现在由 Next.js 在运行时代理，因此在 Zeabur 上只需要给前端服务配置运行时 `BACKEND_URL`，不再依赖构建阶段写死地址。

### 1. PostgreSQL

在 Zeabur 项目里先新增一个 PostgreSQL 服务。

后端会使用这个数据库的连接串作为 `DATABASE_URL`。

### 2. Backend 服务

- 部署来源：GitHub
- 仓库：当前仓库
- Root Directory：`backend`
- 构建方式：使用 `backend/Dockerfile`

建议配置的环境变量：

- `DATABASE_URL`：指向 Zeabur PostgreSQL 的连接串；如果只是 demo，可先不填
- `FASTGPT_BASE_URL`
- `FASTGPT_API_KEY`
- `FASTGPT_DATASET_ID`
- `FASTGPT_DATASET_UPSERT_PATH`
- `FASTGPT_CHAT_PATH`
- `CORS_ORIGINS`：前端公网域名
- `COLLECTION_API_KEY`：保护每日批量采集与人工核验更新接口
- `SERPER_API_KEY`：可选；用于白名单权威站点的线索发现，最终仍回到原文核验

后端 Dockerfile 已改为优先读取 `$PORT`，更适合 Zeabur 的端口分配方式。

每日权威数据更新由外部定时任务调用后端接口：

```text
POST https://<backend-domain>/api/v1/authoritative-ingestion/daily/run?mode=daily&lookback_days=2
X-Collection-Key: <COLLECTION_API_KEY>
```

建议每天凌晨调用一次。首次上线先使用
`mode=backfill&backfill_years=5` 完成五年回补，再切换为每日增量。

### 3. Frontend 服务

- 部署来源：GitHub
- 仓库：当前仓库
- Root Directory：`frontend`
- 构建方式：使用 `frontend/Dockerfile`

建议配置的环境变量：

- `BACKEND_URL`：后端服务地址
- `CSRC_MONITOR_ROOT`：如果需要监管看板，指向容器内挂载目录

如果前后端都放在同一个 Zeabur 项目里，优先使用后端服务的 Private Networking 地址，而不是写死公网域名。

## Zeabur 操作顺序

1. 在 GitHub 创建仓库并推送代码。
2. 在 Zeabur 创建新项目。
3. 如果要正式数据，再先添加 PostgreSQL；如果只是 demo，这步可以先跳过。
4. 从 GitHub 添加 `backend` 服务，并把 Root Directory 设为 `backend`。
5. 再添加一个 `frontend` 服务，并把 Root Directory 设为 `frontend`。
6. 给前端生成 `zeabur.app` 域名，确认页面可访问。
7. 如需正式域名，再绑定自定义域名。

## 当前仓库对 Zeabur 已做的适配

- `frontend/Dockerfile`：可直接作为前端服务构建入口
- `backend/Dockerfile`：可直接作为后端服务构建入口
- `backend/demo.db`：可作为演示数据直接随镜像发布
- `frontend/next.config.ts`：通过 `BACKEND_URL` 做 API rewrite
- 知识库问答已改为后端代理，不需要把 FastGPT Key 暴露到浏览器

## 注意事项

- 爬虫 `enterprise_sentinel` 依赖登录态 Chrome，不适合直接放在 Zeabur 对公网暴露
- 如果要跑监管看板，相关数据目录需要你另外上传或挂载，不能指望 Zeabur 自动带上本地文件
- 如果不配置 PostgreSQL，Zeabur 上会先展示仓库自带的 `demo.db` 内容
- 如果之后改成 PostgreSQL，记得把 `DATABASE_URL` 切过去
