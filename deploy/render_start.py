
"""Start the existing BAINP frontend and API in one container.

Public frontend: 0.0.0.0:$PORT
Internal FastAPI: 127.0.0.1:8000
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "apps/neuroaccess/backend/serve_frontend.py"
API_DIR = ROOT / "apps/neuroaccess/backend"
PORT = int(os.environ.get("PORT", "3000"))

if not (1 <= PORT <= 65535) or PORT == 8000:
    raise SystemExit("PORT must be valid and different from 8000")

if not FRONTEND.is_file():
    raise SystemExit(f"Missing frontend: {FRONTEND}")

if not (API_DIR / "api.py").is_file():
    raise SystemExit("Missing API module")

api = subprocess.Popen(
    [
        sys.executable, "-m", "uvicorn",
        "api:create_app",
        "--factory",
        "--app-dir", str(API_DIR),
        "--host", "127.0.0.1",
        "--port", "8000",
    ],
    cwd=ROOT,
)

frontend = None

try:
    for attempt in range(60):
        if api.poll() is not None:
            raise RuntimeError("FastAPI exited during startup")

        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8000/api/health",
                timeout=2,
            ) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("FastAPI health check timed out")

    # These CLI arguments must be verified against serve_frontend.py.
    frontend = subprocess.Popen(
        [
            sys.executable, str(FRONTEND),

            "--port", str(PORT),
        ],
        cwd=ROOT,
    )

    while True:
        if api.poll() is not None:
            raise RuntimeError("FastAPI stopped unexpectedly")
        if frontend.poll() is not None:
            raise RuntimeError("Frontend stopped unexpectedly")
        time.sleep(1)

finally:
    for process in (frontend, api):
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
