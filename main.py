"""Root launcher for the Gemma QA Analysis application."""

import os
import sys

# Ensure src/ and tests/ are in the python path for clean import resolution
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
TESTS_DIR = os.path.join(ROOT_DIR, "tests")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

if __name__ == "__main__":
    import uvicorn
    from dotenv import load_dotenv
    load_dotenv()
    
    host = os.getenv("SERVER_HOST", "0.0.0.0")
    port = int(os.getenv("SERVER_PORT", "8000"))
    
    print(f"Starting Gemma QA Analysis Web Server on http://{host}:{port}...")
    from api.web_app import app
    uvicorn.run(app, host=host, port=port)
