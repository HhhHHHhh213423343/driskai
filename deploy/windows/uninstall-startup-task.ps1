$ErrorActionPreference = 'Stop'
$taskName = 'D.Risk Company Profile Worker'
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "已移除登录启动任务：$taskName" -ForegroundColor Green
} else {
    Write-Host "未找到任务：$taskName"
}
