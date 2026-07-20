# 公网部署说明

这套部署面向仓库中的 Web 服务部分：

- `frontend`：Next.js 页面与 API 重写层
- `backend`：FastAPI + PostgreSQL
- `db`：PostgreSQL
- `caddy`：公网入口与 HTTPS 证书

`enterprise_sentinel` 爬虫依赖登录态 Chrome 配置，不适合直接公开暴露。更合理的部署方式是：

1. 把爬虫作为内网或单机定时任务运行。
2. 把抓取产物写入数据库或文件目录。
3. 只把 `frontend + backend` 暴露到公网。

## 前提条件

- 一台可被公网访问的 Linux 服务器
- 域名已经解析到服务器公网 IP
- 服务器已安装 Docker Engine 和 Docker Compose Plugin
- 如果要使用监管看板，准备好 `csrc_monitor_deployment_package` 数据目录
- 如果要使用知识库问答，准备好 FastGPT 或兼容接口地址与服务端 API Key

## 目录与文件

- `docker-compose.public.yml`：单机部署编排
- `deploy/Caddyfile`：HTTPS 与反向代理配置
- `.env.public.example`：部署环境变量模板

## 部署步骤

1. 复制环境变量模板。

```bash
cp .env.public.example .env.public
```

2. 编辑 `.env.public`，至少填写：

- `PUBLIC_HOST`
- `POSTGRES_PASSWORD`
- `FASTGPT_BASE_URL`、`FASTGPT_API_KEY`（如果启用知识库问答）
- `CSRC_MONITOR_ROOT_HOST`（如果启用监管看板）

3. 如果你要展示监管措施页面，把本地数据目录放到服务器指定位置，例如：

```bash
mkdir -p ./data/csrc-monitor
```

然后把 `csrc_monitor_deployment_package` 的内容同步到这个目录，保证其中至少包含：

- `api.py`
- `contents/`
- `links/`
- `scan_record.json`
- `change_log.json`

4. 启动服务。

```bash
docker compose -p enterprise-sentinel --env-file .env.public -f docker-compose.public.yml up -d --build
```

5. 查看状态。

```bash
docker compose -p enterprise-sentinel --env-file .env.public -f docker-compose.public.yml ps
docker compose -p enterprise-sentinel --env-file .env.public -f docker-compose.public.yml logs -f
```

这里显式指定了 `-p enterprise-sentinel`，可以避免部署目录名包含中文或特殊字符时，Compose 无法自动推导项目名。

## 对外访问方式

- 页面入口：`https://你的域名`
- 后端健康检查：`https://你的域名/health`
- 后端 API：`https://你的域名/api/v1/...`

前端通过 Next.js rewrite 转发到内部 `backend:8001`，浏览器不需要直接访问容器内网地址。

## 关键环境变量

- `PUBLIC_HOST`：公网域名，Caddy 用它签发证书
- `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD`：PostgreSQL 连接信息
- `FASTGPT_BASE_URL`：FastGPT 或兼容服务根地址
- `FASTGPT_API_KEY`：仅保存在服务端，不再暴露给浏览器
- `FASTGPT_DATASET_UPSERT_PATH`：知识库同步接口路径
- `FASTGPT_CHAT_PATH`：知识库问答接口路径，默认 `/chat/completions`
- `CSRC_MONITOR_ROOT_HOST`：宿主机上的监管数据目录

## 数据与初始化

- FastAPI 启动时会自动建表，但不会自动灌入业务数据。
- 如果数据库目前只在你本机，部署前需要额外做一次导出和导入。
- 如果没有导入数据，页面可以打开，但企业分析与问答结果会为空。

## 建议

- 爬虫和 Web 服务分开部署，避免把浏览器登录态放到公网机器上
- 生产环境不要把 `FASTGPT_API_KEY` 放到 `NEXT_PUBLIC_*` 变量
- 首次上线后先检查：
  - `/health` 是否返回 `{"status":"ok"}`
  - 企业查询接口是否可用
  - 知识库页面是否能正常返回回答
