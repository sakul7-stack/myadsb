"""Backend entry point.

Starts the FastAPI app, mounts the receiver WebSocket + read APIs, and runs a
background task that drops stale aircraft/receivers.

Run:  uvicorn main:app --host 0.0.0.0 --port 8000
   or: python main.py
"""

import asyncio
import logging

from fastapi import FastAPI

from config import settings
from state import store
from ws_server import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ADS-B Network Backend")
app.include_router(router)


async def _cleanup_loop():
    while True:
        await asyncio.sleep(settings.CLEANUP_INTERVAL_S)
        dropped_ac, dropped_rx = store.cleanup()
        if dropped_ac or dropped_rx:
            logger.info("cleanup: -%d aircraft, -%d receivers", dropped_ac, dropped_rx)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_cleanup_loop())
    logger.info("backend up on ws://%s:%s/ws/adsb", settings.WS_HOST, settings.WS_PORT)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.WS_HOST, port=settings.WS_PORT)
