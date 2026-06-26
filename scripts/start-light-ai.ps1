param(
    [switch]$SelfCheck
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $Root "runtime\logs"
$LogPath = Join-Path $LogDir "launcher.log"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Set-Location $Root
$env:PYTHONUTF8 = "1"

function Write-LaunchLog($Message) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LogPath -Value "[$stamp] $Message" -Encoding UTF8
}

try {
    Write-LaunchLog "Starting Light Shelf AI from $Root"

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $pythonArgs = @("launch_light_ai.py")
        if ($SelfCheck) { $pythonArgs += "--check" }
        & $python.Source @pythonArgs 2>&1 | Tee-Object -FilePath $LogPath -Append
        exit $LASTEXITCODE
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $pythonArgs = @("-3", "launch_light_ai.py")
        if ($SelfCheck) { $pythonArgs += "--check" }
        & $py.Source @pythonArgs 2>&1 | Tee-Object -FilePath $LogPath -Append
        exit $LASTEXITCODE
    }

    throw "Python was not found. Please install Python 3."
}
catch {
    Write-LaunchLog "ERROR: $($_.Exception.Message)"
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("Launch failed.`n`n$($_.Exception.Message)`n`nLog: $LogPath", "Light Shelf AI", "OK", "Error") | Out-Null
    exit 1
}
