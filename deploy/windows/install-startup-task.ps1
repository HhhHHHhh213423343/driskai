param(
    [switch]$StartNow
)

. (Join-Path $PSScriptRoot 'common.ps1')

$taskName = 'D.Risk Company Profile Worker'
$runner = Join-Path $PSScriptRoot 'run-worker.ps1'
$powerShell = (Get-Command powershell.exe).Source
$action = New-ScheduledTaskAction -Execute $powerShell -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive `
    -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Principal $principal `
    -Settings $settings `
    -Description '轮询 D.Risk 企业全景任务，使用 Windows Edge 登录态采集企业预警通。' `
    -Force | Out-Null

if ($StartNow) { Start-ScheduledTask -TaskName $taskName }
Write-Host "已安装登录启动任务：$taskName" -ForegroundColor Green
