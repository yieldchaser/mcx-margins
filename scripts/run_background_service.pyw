"""
Blue Margin — Silent Windows Background Automation Service (.pyw)
scripts/run_background_service.pyw

Runs completely invisible in the background on Windows:
- Zero popups, zero terminal windows, zero interruption.
- Automatically snapshots market every 30 minutes during MCX hours (09:00 to 23:30 IST Mon-Fri).
- Automatically keeps live_bridge.py WebSocket server running on ws://127.0.0.1:8765.
- Silently pushes fresh data to GitHub Pages.
"""

import os
import sys
import time
import subprocess
from datetime import datetime

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON_EXE = os.path.join(os.path.dirname(sys.executable), "python.exe")
LOG_FILE = os.path.join(REPO_DIR, "data", "background_service.log")

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

log("Starting Blue Margin Silent Background Automation Service...")

# Launch live_bridge.py as a persistent background subprocess
bridge_proc = None
def ensure_bridge_alive():
    global bridge_proc
    if bridge_proc is None or bridge_proc.poll() is not None:
        try:
            bridge_script = os.path.join(REPO_DIR, "scripts", "live_bridge.py")
            # CREATE_NO_WINDOW = 0x08000000 ensures zero console window
            bridge_proc = subprocess.Popen(
                [PYTHON_EXE, bridge_script],
                cwd=REPO_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            log(f"Started live_bridge daemon (PID: {bridge_proc.pid})")
        except Exception as e:
            log(f"Error starting live_bridge: {e}")

last_snapshot_time = 0
SNAPSHOT_INTERVAL_SECONDS = 30 * 60 # Every 30 minutes

while True:
    try:
        now = datetime.now()
        weekday = now.weekday() # 0 = Monday, 4 = Friday
        minute_of_day = now.hour * 60 + now.minute
        
        # MCX Trading Window: Monday-Friday, 09:00 to 23:35 IST
        is_trading_hours = (0 <= weekday <= 4) and (9 * 60 <= minute_of_day <= 23 * 60 + 35)
        
        # Ensure WebSocket bridge is running during trading hours
        if is_trading_hours:
            ensure_bridge_alive()
            
            # Check if it's time to run snapshot
            if (time.time() - last_snapshot_time) >= SNAPSHOT_INTERVAL_SECONDS:
                log("Triggering scheduled market snapshot...")
                snapshot_script = os.path.join(REPO_DIR, "scripts", "auto_market_snapshot.py")
                res = subprocess.run(
                    [PYTHON_EXE, snapshot_script],
                    cwd=REPO_DIR,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    capture_output=True,
                    text=True
                )
                last_snapshot_time = time.time()
                log(f"Snapshot execution finished (exit code {res.returncode})")
        else:
            # Outside market hours: terminate bridge if running to conserve resources
            if bridge_proc and bridge_proc.poll() is None:
                bridge_proc.terminate()
                bridge_proc = None
                log("Market closed. Suspended live bridge daemon.")
                
        # Sleep for 60 seconds before next heartbeat check
        time.sleep(60)
        
    except Exception as e:
        log(f"Exception in service loop: {e}")
        time.sleep(60)
