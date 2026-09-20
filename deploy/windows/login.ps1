. (Join-Path $PSScriptRoot 'common.ps1')

$edge = Get-EdgePath
$profileDir = Get-WorkerProfileDir
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

Write-Host '正在打开 D.Risk 专用 Edge 会话。' -ForegroundColor Cyan
Write-Host '请登录企业预警通，确认可打开企业详情页，然后关闭这个 Edge 窗口。'
$arguments = @(
    "--user-data-dir=`"$profileDir`"",
    '--profile-directory=Default',
    'https://www.qyyjt.cn'
)
Start-Process -FilePath $edge -ArgumentList $arguments -Wait

Write-Host '专用登录会话已保存。请继续运行 preflight.ps1。' -ForegroundColor Green
