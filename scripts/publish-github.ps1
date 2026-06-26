param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteUrl
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".git")) {
    throw "このフォルダはGitリポジトリではありません。"
}

git branch -M main

$existing = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0 -and $existing) {
    git remote set-url origin $RemoteUrl
} else {
    git remote add origin $RemoteUrl
}

git push -u origin main
