param(
    [switch]$Once
)

. (Join-Path $PSScriptRoot 'common.ps1')

$root = Get-ProjectRoot
$python = Get-WorkerPython
$edge = Get-EdgePath
$profileDir = Get-WorkerProfileDir
$logDir = Get-WorkerLogDir
$apiUrl = if ($env:DRISK_API_URL) { $env:DRISK_API_URL.TrimEnd('/') } else { '' }
$key = if ($env:COLLECTION_API_KEY) { $env:COLLECTION_API_KEY } else { '' }

if (-not $apiUrl) { throw '未配置 DRISK_API_URL，请先运行 configure.ps1。' }
if ($key.Length -lt 32) { throw '未配置有效的 COLLECTION_API_KEY，请先运行 configure.ps1。' }
if (-not (Test-Path -LiteralPath (Join-Path $profileDir 'Default'))) {
    throw '未找到专用 Edge 登录会话，请先运行 login.ps1。'
}

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$transcript = Join-Path $logDir ("worker-{0}.log" -f (Get-Date -Format 'yyyyMMdd'))
Start-Transcript -Path $transcript -Append | Out-Null
Push-Location $root
try {
    $arguments = @(
        '-u', '-m', 'enterprise_sentinel.company_profile.agent',
        '--api-url', $apiUrl,
        '--user-data-dir', $profileDir,
        '--profile-directory', 'Default',
        '--browser-path', $edge,
        '--use-live-profile'
    )
    if ($Once) { $arguments += '--once' }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Worker 异常退出，代码：$LASTEXITCODE" }
} finally {
    Pop-Location
    Stop-Transcript | Out-Null
}
