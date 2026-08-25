import os

import uvicorn

if __name__ == "__main__":
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=environment == "development",
        workers=1
    )
