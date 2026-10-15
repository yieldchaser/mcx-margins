# Blue Margin — Stop Silent Background Service
# scripts/stop_background_service.ps1

Write-Host "Stopping Blue Margin background services..." -ForegroundColor Cyan

# Stop run_background_service.pyw and live_bridge.py
Get-WmiObject Win32_Process | Where-Object { 
    $_.CommandLine -like "*run_background_service.pyw*" -or 
    $_.CommandLine -like "*live_bridge.py*" 
} | ForEach-Object {
    Write-Host "Terminating PID $($_.ProcessId): $($_.CommandLine)" -ForegroundColor Yellow
    Stop-Process -Id $_.ProcessId -Force
}

Write-Host "All Blue Margin background services stopped successfully." -ForegroundColor Green
