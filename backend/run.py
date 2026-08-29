import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"[Startup] Launching Bytelytic FastAPI server on 0.0.0.0:{port} ...")
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, log_level="info")
