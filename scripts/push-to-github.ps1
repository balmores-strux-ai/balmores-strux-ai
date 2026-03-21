# Run after installing Git: https://git-scm.com/download/win
# Usage: .\scripts\push-to-github.ps1 https://github.com/YOUR_USER/YOUR_REPO.git

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

$remote = $args[0]
if (-not $remote) {
  Write-Host "Usage: .\scripts\push-to-github.ps1 https://github.com/YOUR_USER/YOUR_REPO.git"
  exit 1
}

$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
  Write-Host "Git not found. Install Git for Windows, then re-open this terminal."
  exit 1
}

if (-not (Test-Path ".git")) {
  git init
  git branch -M main
}

git add -A
git status
$msg = Read-Host "Commit message (Enter for default)"
if ([string]::IsNullOrWhiteSpace($msg)) { $msg = "BALMORES STRUX AI — Render-ready" }
git commit -m $msg

$hasOrigin = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
  git remote add origin $remote
}

git push -u origin main
Write-Host "Done. Next: Render → New → Blueprint → select this repo."
