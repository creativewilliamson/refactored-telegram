# start.ps1 - build the data and pages in Docker, serve the site, print the URL.
# Usage: .\start.ps1
# The first run downloads public store and Census data into data\cache
# (a few minutes). Later runs reuse the cache.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker isn't running. Start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

Write-Host "Building Vet Day Deals (data + pages) and starting the web server..."
$env:BUILDKIT_PROGRESS = 'quiet'
docker compose --progress quiet up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "The build failed. See: docker compose logs build" -ForegroundColor Red
    exit 1
}

$url = 'http://localhost:8095/'
$deadline = (Get-Date).AddMinutes(5)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -eq 200) {
            Write-Host ""
            Write-Host "Vet Day Deals is running. Open $url" -ForegroundColor Green
            exit 0
        }
    } catch { }
    Start-Sleep -Seconds 2
}
Write-Host "The site did not answer in time. See: docker compose logs web" -ForegroundColor Red
exit 1
