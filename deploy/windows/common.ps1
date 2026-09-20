$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-ProjectRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

function Get-WorkerPython {
    $python = Join-Path (Get-ProjectRoot) '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw '未找到 .venv\Scripts\python.exe，请先运行 setup.ps1。'
    }
    return $python
}

function Get-EdgePath {
    $candidates = @(
        @(
            $(if (${env:ProgramFiles(x86)}) { Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe' }),
            $(if ($env:ProgramFiles) { Join-Path $env:ProgramFiles 'Microsoft\Edge\Application\msedge.exe' }),
            $(if ($env:LOCALAPPDATA) { Join-Path $env:LOCALAPPDATA 'Microsoft\Edge\Application\msedge.exe' })
        ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    )
    if (-not $candidates) {
        throw '未找到 Microsoft Edge。'
    }
    return $candidates[0]
}

function Get-WorkerProfileDir {
    if ($env:DRISK_EDGE_PROFILE_DIR) {
        return [System.IO.Path]::GetFullPath($env:DRISK_EDGE_PROFILE_DIR)
    }
    return (Join-Path (Get-ProjectRoot) '.runtime\edge-profile')
}

function Get-WorkerLogDir {
    return (Join-Path (Get-ProjectRoot) '.runtime\logs')
}
