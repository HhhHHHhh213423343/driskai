# Zeabur 部署

本仓库使用同一 GitHub 仓库部署两个服务。两个服务都保持仓库根目录为构建根目录，并按下面的名称创建；Zeabur 会自动匹配同名 Dockerfile。

## 1. Backend

- 服务名：`backend`
- Dockerfile：`Dockerfile.backend`
- 端口：使用 Zeabur 注入的 `PORT`
- 可选环境变量：`D_RISK_DATABASE=/app/backend/demo.db`

镜像自带公开演示数据。容器重新部署时，运行期新增的数据可能重置；正式环境应将数据库迁移到持久化存储。

## 2. Frontend

- 服务名：`frontend`
- Dockerfile：`Dockerfile.frontend`
- 环境变量：`BACKEND_URL=<backend 的 Zeabur 内网地址>`

`BACKEND_URL` 仅在 Next.js 服务端代理中使用，不会暴露到浏览器。两个服务部署完成后，只需要为 `frontend` 绑定公网域名。

## 部署顺序

1. 在 Zeabur 中连接本 GitHub 仓库。
2. 创建名为 `backend` 的服务并等待健康启动。
3. 创建名为 `frontend` 的服务，将 `BACKEND_URL` 设置为 backend 的内网地址。
4. 为 frontend 生成或绑定域名。

如果服务名无法保持为 `backend` / `frontend`，可分别设置：

- `ZBPACK_DOCKERFILE_NAME=backend`
- `ZBPACK_DOCKERFILE_NAME=frontend`

该变量只填写后缀，不填写完整文件名。
