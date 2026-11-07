# run-unattended.ps1 - start a build run and walk away (overnight or away).
# Usage: open this folder in PowerShell and run  .\run-unattended.ps1
# Before you leave: make sure the PC won't sleep.
# To stop early: create a file named AGENT_STOP in this folder.
# To redirect: write instructions in STEER.md.
# Progress streams to run.log; the result lands in RUN-REPORT.md.

Set-Location $PSScriptRoot

# --- Preflight ---
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Host "Claude Code isn't installed or isn't on PATH." -ForegroundColor Red; exit 1
}
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker isn't running. Start Docker Desktop and try again." -ForegroundColor Red; exit 1
}
if (-not ((claude mcp list 2>&1 | Out-String) -match 'playwright')) {
    Write-Host "Adding the Playwright MCP..." -ForegroundColor Yellow
    claude mcp add playwright npx @playwright/mcp@latest
}
if (Test-Path AGENT_STOP) {
    Write-Host "AGENT_STOP exists. Delete it to start a run." -ForegroundColor Red; exit 1
}

# --- The goal (filled in by the planning chat) ---
$goal = @'
/goal Every feature in FEATURES.json has passes true with browser evidence in evidence/, the evaluator subagent returned PASS on the final build, and RUN-REPORT.md is written per CLAUDE.md. Or stop after 30 hours or 600 turns and write RUN-REPORT.md saying the limit ended the run. No files outside this folder are changed.
'@

Write-Host "Run started $(Get-Date -Format 'yyyy-MM-dd HH:mm'). Watching: Get-Content run.log -Wait" -ForegroundColor Green

# --- Run headless in auto mode ---
# Let background tasks (like a long evaluator round) finish instead of
# being killed after 10 minutes.
$env:CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS = "0"
# [verify on first run: flag name via  claude --help ]
claude -p --permission-mode auto $goal --output-format stream-json --verbose > run.log

Write-Host "Run finished $(Get-Date -Format 'yyyy-MM-dd HH:mm'). Open RUN-REPORT.md." -ForegroundColor Green
