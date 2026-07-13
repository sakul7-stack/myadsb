"""FastAPI endpoints receivers and clients use.

Receiver protocol (matches adsb-network-test/client):
  1. connect to  ws://host:port/ws/adsb
  2. send  {"type": "receiver_info", "client_id": ..., "receiver_info": {...}}
  3. stream {"type": "sbs_message", "message": "<SBS line>", ...}

Read APIs return current live state as JSON.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from state import store
from processor import MessageProcessor

logger = logging.getLogger(__name__)

router = APIRouter()
processor = MessageProcessor()


def _authenticate(client_id, receiver_info):
    """Accept a receiver. TODO: check api_key against the receivers table."""
    return bool(client_id) and receiver_info is not None


@router.websocket("/ws/adsb")
async def adsb_ws(websocket: WebSocket):
    await websocket.accept()
    station_id = None
    try:
        hello = json.loads(await websocket.receive_text())
        if hello.get("type") != "receiver_info":
            await websocket.close()
            return

        station_id = hello.get("client_id")
        info = hello.get("receiver_info")
        if not _authenticate(station_id, info):
            await websocket.send_text(json.dumps({"status": "rejected"}))
            await websocket.close()
            return

        store.receiver_online(station_id, info)
        await websocket.send_text(json.dumps({"status": "connected", "client_id": station_id}))
        logger.info("Receiver %s online", station_id)

        while True:
            msg = json.loads(await websocket.receive_text())
            if msg.get("type") != "sbs_message":
                continue
            await processor.process({
                "raw_message": msg.get("message", ""),
                "receiver_id": station_id,
                "timestamp": datetime.utcnow().isoformat(),
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error (%s): %s", station_id, e)
    finally:
        if station_id:
            store.receiver_offline(station_id)
            logger.info("Receiver %s offline", station_id)


@router.get("/api/aircraft")
async def get_aircraft():
    return {"aircraft": store.snapshot(), "count": len(store.aircraft)}


@router.get("/api/receivers")
async def get_receivers():
    return {"receivers": store.receivers}


@router.get("/api/status")
async def get_status():
    return {
        "aircraft": len(store.aircraft),
        "receivers": len(store.receivers),
        "messages": processor.count,
        "timestamp": datetime.utcnow().isoformat(),
    }
