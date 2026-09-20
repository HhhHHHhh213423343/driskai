param(
    [string]$ApiUrl = 'https://d-risk-ai.zeabur.app'
)

. (Join-Path $PSScriptRoot 'common.ps1')

$secureKey = Read-Host '请输入与 Zeabur 后端一致的 COLLECTION_API_KEY' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if ([string]::IsNullOrWhiteSpace($plainKey) -or $plainKey.Length -lt 32) {
        throw 'COLLECTION_API_KEY 建议至少 32 位。'
    }
    [Environment]::SetEnvironmentVariable('DRISK_API_URL', $ApiUrl.TrimEnd('/'), 'User')
    [Environment]::SetEnvironmentVariable('COLLECTION_API_KEY', $plainKey, 'User')
    $env:DRISK_API_URL = $ApiUrl.TrimEnd('/')
    $env:COLLECTION_API_KEY = $plainKey
} finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

Write-Host '已写入当前 Windows 用户的 Worker 配置。' -ForegroundColor Green
Write-Host '密钥不会写入代码库或任务计划参数。'
