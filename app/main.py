import uvicorn
from fastapi import FastAPI
from adapters.http_api import api_router
from adapters.mqtt_client import start_mqtt, stop_mqtt
from adapters.ws import router as ws_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from domain.SpotAllocator import SpotAllocator
from deps import SessionLocal
from domain.SpotAllocator import SpotAllocatorIndexBuilder,SpotIndex

""" 
== MQTT ==
Es un protocolo de mensajería súper liviano pensado para dispositivos (IoT): cámaras, sensores, 
barreras, etc. En vez de que un dispositivo le envíe datos directamente a otro, todos hablan 
con un “broker” (un servidor MQTT, ej. Mosquitto).

Idea clave: publish/subscribe (publicar/suscribirse) por tópicos de texto.
Ejemplo de tópicos:
    sensors/gate-01/events (los sensores publican eventos)
    actuators/gate-01/commands (el Access Controller publica comandos)

En este contexto, un cliente MQTT es cualquier programa que se conecte al broker para publicar
mensajes o suscribirse a recibirlos. Cuando un programa se suscribe a un broker busca ser 
notificado de todos los mensajes de cierto topico. En este contexto:

    -Una camara o sensor es un cliente MQTT que publica eventos (vehiculo entrante)
    -El programa Access Controller (AC) es un cliente MQTT que se suscribe a eventos (de los
    sensores) y publica comandos (abrir/cerrar, etc)
    -La barrera es otro cliente MQTT que se suscribe a comandos

El AC se suscribe al broker de MQTT en adapters.mqtt_client.py.
"""

app = FastAPI(title="UniParking Access Controller", version="0.1.0")
app.include_router(api_router, prefix="/v1")
app.include_router(ws_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/ws/test")
def ws_test():
    return FileResponse("static/ws-dashboard.html", media_type="text/html")

@app.get("/ws/spot-feed")
def ws_spot():
    return FileResponse("static/ws-spot.html", media_type="text/html")

@app.on_event("startup")
async def on_startup():
    # 1) Construir el/los KD-Tree desde la BDD
    async with SessionLocal() as session:
        builder = SpotAllocatorIndexBuilder()
        allocator = SpotAllocator(builder)
        spot_index: SpotIndex = await allocator.find_spot(session, car_type="GENERAL")
        app.state.spot_index = spot_index

    # 2) Tu callback MQTT tal cual lo tenías
    async def on_event(ev: dict):
        if ev.get("type") != "PLATE_READ":
            return
        plate = ev.get("payload", {}).get("plate")
        print("[AC] event:", ev)

    # 3) Arrancar MQTT
    await start_mqtt(on_event)

@app.on_event("shutdown")
async def on_shutdown():    
    await stop_mqtt()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
