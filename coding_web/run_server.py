import sys
sys.path.insert(0, r"f:\agents\Demox-main\team-old")
sys.path.insert(0, r"f:\agents\Demox-main\team-old\src")

import uvicorn
uvicorn.run(
    "coding_web.backend.main:app",
    host="127.0.0.1",
    port=8000,
    log_level="info",
)
