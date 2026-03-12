from fastapi import FastAPI
import uvicorn
import os
from config.config import config
import signals.create as create

app = FastAPI()
@app.get("/")
def read_root():
    db_config = config.database
    return {"host": db_config.get("host", "No host found in config")}

@app.post("/signal")
def create_signal(request: dict):

    return create.create_signal(request=request)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000)) 
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
