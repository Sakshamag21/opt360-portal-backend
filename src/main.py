from fastapi import FastAPI
import uvicorn
from config.config import config
import signals.create as create

app = FastAPI()
@app.get("/")
def read_root():
    db_config = config.database
    return {"host": db_config.get("host", "No host found in config")}

@app.post("/signal/create")
def create_signal(request: dict):

    return create.create_signal(request=request)
@app.get("/signal/info/{feature_id}")
def get_signal_info(feature_id: str):
    import signals.info as info
    return info.get_feature_signals(feature_id=feature_id)

if __name__ == "__main__": 
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
