# run-watched.ps1 - start a build run you can watch and steer.
# Usage: open this folder in PowerShell and run  .\run-watched.ps1
# Stop anytime with  /goal clear  (or Ctrl+C).

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

# --- The goal (filled in by the planning chat) ---
$goal = @'
/goal Every feature in FEATURES.json has passes true with browser evidence in evidence/, the evaluator subagent returned PASS on the final build, and RUN-REPORT.md is written per CLAUDE.md. Or stop after 30 hours or 600 turns and write RUN-REPORT.md saying the limit ended the run. No files outside this folder are changed.
'@

# --- Start Claude Code in auto mode with the goal set ---
# [verify on first run: flag name via  claude --help ]
claude --permission-mode auto $goal
