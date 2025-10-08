import asyncio
import uvicorn
from fastapi import FastAPI
from adapters.http_api import api_router
from adapters.mqtt_client import start_mqtt, stop_mqtt

app = FastAPI(title="UniParking Access Controller", version="0.1.0")
app.include_router(api_router, prefix="/v1")

@app.on_event("startup")
async def on_startup():
    await start_mqtt()

@app.on_event("shutdown")
async def on_shutdown():    
    await stop_mqtt()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
