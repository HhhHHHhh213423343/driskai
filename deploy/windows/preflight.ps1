. (Join-Path $PSScriptRoot 'common.ps1')

$checks = @()
function Add-Check([string]$Name, [bool]$Ok, [string]$Detail) {
    $script:checks += [pscustomobject]@{ Name = $Name; Ok = $Ok; Detail = $Detail }
}

try { Add-Check 'Python Worker' $true (Get-WorkerPython) } catch { Add-Check 'Python Worker' $false $_.Exception.Message }
try { Add-Check 'Microsoft Edge' $true (Get-EdgePath) } catch { Add-Check 'Microsoft Edge' $false $_.Exception.Message }

$profileDir = Get-WorkerProfileDir
$profileReady = Test-Path -LiteralPath (Join-Path $profileDir 'Default')
Add-Check '专用 Edge Profile' $profileReady $(if ($profileReady) { $profileDir } else { '请先运行 login.ps1' })

$apiUrl = if ($env:DRISK_API_URL) { $env:DRISK_API_URL.TrimEnd('/') } else { '' }
$key = if ($env:COLLECTION_API_KEY) { $env:COLLECTION_API_KEY } else { '' }
Add-Check 'DRISK_API_URL' (-not [string]::IsNullOrWhiteSpace($apiUrl)) $apiUrl
Add-Check 'COLLECTION_API_KEY' ($key.Length -ge 32) $(if ($key.Length -ge 32) { '已配置' } else { '请运行 configure.ps1' })

if ($apiUrl) {
    try {
        $health = Invoke-RestMethod -Uri "$apiUrl/health" -Method Get -TimeoutSec 15
        Add-Check 'D.Risk 健康检查' ($health.status -eq 'ok') "$apiUrl/health"
    } catch {
        Add-Check 'D.Risk 健康检查' $false $_.Exception.Message
    }
}

$checks | Format-Table -AutoSize
if (@($checks | Where-Object { -not $_.Ok }).Count -gt 0) {
    throw '预检未通过，请先处理上表中的失败项。'
}
Write-Host '预检通过。可运行 run-worker.ps1 开始轮询任务。' -ForegroundColor Green
