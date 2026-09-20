. (Join-Path $PSScriptRoot 'common.ps1')

$root = Get-ProjectRoot
$venv = Join-Path $root '.venv'
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts\python.exe'))) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 -m venv $venv
    } else {
        $python = Get-Command python -ErrorAction SilentlyContinue
        if (-not $python) { throw '未找到 Python 3，请先安装 Python 3.11 或更高版本。' }
        & $python.Source -m venv $venv
    }
}

$workerPython = Get-WorkerPython
& $workerPython -m pip install -r (Join-Path $root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '采集 Worker 依赖安装失败。' }

Write-Host 'Windows 采集 Worker 运行环境已就绪。' -ForegroundColor Green
Write-Host '下一步：运行 login.ps1，在专用 Edge 会话中登录企业预警通。'
