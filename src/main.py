from fastapi import FastAPI
import uvicorn
import os

from routes import routers

# Initialize FastAPI application
app = FastAPI(
    title="Operator360 API",
    description="API for managing signals and features in Operator360 system",
    version="1.0.0"
)

# Include all routers with /api prefix
for router in routers:
    app.include_router(router, prefix="/api")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
