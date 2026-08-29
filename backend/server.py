import os
import sys

# Ensure current directory is first in sys.path
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir not in sys.path:
    sys.path.insert(0, cur_dir)

import uvicorn
from src.main import app

if __name__ == "__main__":
    port_str = os.environ.get("PORT", "8000")
    try:
        port = int(port_str)
    except Exception:
        port = 8000
    print(f"[Server] Starting FastAPI backend on 0.0.0.0:{port} ...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
