param(
    [string]$Message = "Update classroom AI assistant"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repoRoot

$env:GIT_SSH_COMMAND = 'ssh -i "C:\Users\Doublethree\.ssh\codex_github_ed25519" -o IdentitiesOnly=yes'

$status = git status --porcelain
if (-not $status) {
    Write-Host "No changes to push."
    exit 0
}

git add .
git commit -m $Message
git push
