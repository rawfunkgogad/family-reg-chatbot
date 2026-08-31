import uvicorn
import sys
import os
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))
    
    print("=" * 65)
    print(" [Family Registry Practice AI Assistant Server Started]")
    print(f" Access URL: http://{host}:{port}")
    print("=" * 65)
    
    uvicorn.run("app:app", host=host, port=port, reload=False, app_dir=str(backend_dir))
