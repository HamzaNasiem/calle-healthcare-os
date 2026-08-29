import os
import sys

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import uvicorn
from src.main import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[Startup] Launching Bytelytic FastAPI server on 0.0.0.0:{port} ...", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
