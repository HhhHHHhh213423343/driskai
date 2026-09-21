# D.Risk 企业全景 Windows 采集 Worker

企业全景的网页、任务和快照仍保存在现有 `frontend + backend + PostgreSQL` 服务器。Windows Worker 主动通过 HTTPS 领取任务，使用专用 Edge Profile 采集企业预警通，再上传规范化 JSON 和最终 Excel。服务器不保存企业预警通密码、Cookie 或验证码。

## 1. 部署前提

- Windows 10/11 可以正常打开企业预警通；
- Windows 可以通过 HTTPS 访问 D.Risk 前后端；
- 已安装 Microsoft Edge 和 Python 3.11 或更高版本；
- 后端已部署本版本的 `/api/v1/company-profile/worker/*` 接口；
- Zeabur backend 已配置至少 32 位的 `COLLECTION_API_KEY`。

后端根路径返回 `404 Not Found` 不代表服务失败。正式健康检查地址是：

```text
https://<D.Risk 后端域名>/health
```

## 2. Windows 首次安装

将项目放到 Windows 本地磁盘，在 PowerShell 中进入 `deploy\windows`，按顺序运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
powershell -ExecutionPolicy Bypass -File .\login.ps1
powershell -ExecutionPolicy Bypass -File .\configure.ps1 -ApiUrl 'https://d-risk-ai.zeabur.app'
powershell -ExecutionPolicy Bypass -File .\preflight.ps1
```

`login.ps1` 会打开独立的 Edge Profile。请在其中完成企业预警通登录，打开任意企业详情页验证权限，然后关闭该 Edge 窗口。登录失效或出现验证码时重新运行该脚本；Worker 不会绕过验证码。

Windows Worker 直接使用这份专用 Edge Profile，以保留企业预警通刷新后的 Cookie。运行 Worker 前必须关闭 `login.ps1` 打开的专用 Edge 窗口；普通浏览器窗口不应使用该专用 Profile。

`configure.ps1` 将 D.Risk 地址和采集密钥写入当前 Windows 用户的环境变量，密钥不会写入代码库或任务计划参数。

## 3. 单次验收

先在 D.Risk 搜索下列任一安全别名：

- `上海携程金融信息服务有限公司`
- `携程金融信息服务有限公司`
- `上海携程金融信息服务`
- `携程金融信息服务`

这些输入均会在入库前映射为法定全称。输入较短的 `携程金融` 时，页面只显示候选并要求用户确认，不会立即建立采集任务。

随后在 Windows 运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\run-worker.ps1 -Once
```

验收标准：

1. 任务状态从“等待 Windows 采集节点”变为“正在采集”；
2. 固定 8 个模块全部为 `PASS` 或 `EMPTY_VALID`；
3. 工商变更包含独立的“变更前”和“变更后”列；
4. 如页面显示数量大于实际采集数量，模块标记为 `PARTIAL` 且不覆盖正式快照；
5. Excel 文件只包含固定顺序的 8 个 Sheet；
6. 24 小时内再次搜索直接复用完整快照，点击“重新采集”才强制新建任务。

## 4. 设为 Windows 登录后自动运行

单次验收通过后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install-startup-task.ps1 -StartNow
```

任务计划名称为 `D.Risk Company Profile Worker`。Worker 主动出站访问 D.Risk，Windows 不需要开放入站端口。日志保存在 `.runtime\logs`。

如需停用登录启动任务：

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-startup-task.ps1
```

## 5. 采集和发布规则

- 采集器按 `overview`、`creditData`、`monitor` 三个页面族复用标签页；
- SOP 版本为 `QYYJT-COMPANY-PROFILE-V3.2`；
- 企业名称、企业代码与页面身份必须一致；
- 头像首字和已知企业标签会进行结构化清洗；
- 任一模块失败或 `PARTIAL` 时，本轮不发布新快照；
- 登录、验证码、账号权限和区域访问问题不自动绕过。

macOS LaunchAgent 模板仍保留在 `deploy/com.drisk.company-profile-agent.plist.example`，但当前生产路径以 Windows Worker 为准。
