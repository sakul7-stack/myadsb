# Receiver Client

Runs next to a receiver (dump1090) and forwards its SBS stream to the `backend`
over WebSocket. One of these runs per receiver site.

## Setup

1. Edit `config.json`:
   - `server_ip` / `server_port` — where the backend runs
   - `receiver_info` — this site's location (lat/lon/alt)
   - `client_id` — a unique name for this receiver
2. Install and run:

```
pip install -r requirements.txt
python client.py
```

When it asks for the SBS source, give your dump1090 IP (port 30003), or type
`test` to send fake data.

## Protocol

Matches `backend/ws_server.py`:

1. connect to `ws://server:port/ws/adsb`
2. send `{"type": "receiver_info", "client_id": ..., "receiver_info": {...}}`
3. stream `{"type": "sbs_message", "message": "<SBS line>", ...}`
