#Requires -Version 5.1
<#
  Pushes this project to GitHub in one shot after you authenticate once.

  Option A (easiest): run in PowerShell
    gh auth login
    .\scripts\auto-push-to-github.ps1

  Option B (token): create a classic PAT with "repo" scope at github.com/settings/tokens
    setx GH_TOKEN "ghp_your_token_here"
    Close and reopen PowerShell, then:
    .\scripts\auto-push-to-github.ps1

  Option C: put the PAT alone in a file gh_token.txt in the project root (file is gitignored),
    run this script once, then delete gh_token.txt.

  Optional argument: repository name on your account (default: balmores-strux-ai)
    .\scripts\auto-push-to-github.ps1 my-repo-name
#>

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

$git = "C:\Program Files\Git\bin\git.exe"
if (-not (Test-Path $git)) {
  $git = "git"
}

$gh = "${env:ProgramFiles}\GitHub CLI\gh.exe"
if (-not (Test-Path $gh)) {
  $gh = "gh"
}

$repoName = $args[0]
if ([string]::IsNullOrWhiteSpace($repoName)) {
  $repoName = "balmores-strux-ai"
}

function Ensure-GhAuth {
  & $gh auth status 2>$null
  if ($LASTEXITCODE -eq 0) {
    return
  }

  if ($env:GH_TOKEN) {
    Write-Host "Logging in with GH_TOKEN from environment..."
    $env:GH_TOKEN | & $gh auth login --hostname github.com --with-token
    return
  }

  $tokenFile = Join-Path $repoRoot "gh_token.txt"
  if (Test-Path $tokenFile) {
    Write-Host "Logging in with gh_token.txt (delete this file after push)..."
    $raw = (Get-Content $tokenFile -Raw).Trim()
    $raw | & $gh auth login --hostname github.com --with-token
    return
  }

  Write-Host ""
  Write-Host "GitHub login required. Choose one:"
  Write-Host "  1) Run:  gh auth login"
  Write-Host "  2) Set environment variable GH_TOKEN (classic PAT with 'repo' scope)"
  Write-Host "  3) Create gh_token.txt in project root with PAT on one line (gitignored)"
  Write-Host ""
  exit 1
}

# Local commit if there are changes
& $git config user.name "BALMORES STRUX AI" 2>$null
& $git config user.email "balmores-strux-ai@users.noreply.github.com" 2>$null

& $git add -A
$porcelain = & $git status --porcelain
if ($porcelain) {
  & $git commit -m "Update: BALMORES STRUX AI"
}

Ensure-GhAuth

$hasOrigin = $false
try {
  $null = & $git remote get-url origin 2>$null
  if ($LASTEXITCODE -eq 0) { $hasOrigin = $true }
} catch {
  $hasOrigin = $false
}

if (-not $hasOrigin) {
  Write-Host "Creating GitHub repo '$repoName' and pushing..."
  & $gh repo create $repoName --public --source=. --remote=origin --push --description "BALMORES STRUX AI — structural FEM + chat + Render"
} else {
  Write-Host "Remote 'origin' exists — pushing main..."
  & $git push -u origin main
}

Write-Host "Done. Open Render and connect this repository for deployment."
