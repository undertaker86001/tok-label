# Mining Audio ML Backend Service Start Script
Write-Host "Starting Mining Audio ML Backend Service..." -ForegroundColor Green
Write-Host ""

# Activate virtual environment if it exists
$venvPath = "..\..\venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & $venvPath
} else {
    Write-Host "Warning: Virtual environment not found. Using system Python." -ForegroundColor Red
}

# Start the service
Write-Host "Starting the ML backend service on port 9090..." -ForegroundColor Yellow
python _wsgi.py --host 0.0.0.0 --port 9090 --debug

Write-Host ""
Write-Host "Service stopped." -ForegroundColor Green