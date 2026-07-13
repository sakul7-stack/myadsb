# Backend — ADS-B Multi-Receiver Network + MLAT

This backend collects ADS-B from **several receivers** and is built to do **MLAT**
(finding an aircraft from timing across receivers). It is separate from `../plane`,
which is the single local-receiver website.


## Files

| file            | job |
|-----------------|-----|
| `main.py`       | FastAPI app + entry point, starts cleanup loop |
| `config.py`     | settings (env-overridable) |
| `models.py`     | SQLAlchemy tables for history |
| `sbs.py`        | parse one SBS/BaseStation line |
| `state.py`      | live aircraft + receiver store |
| `processor.py`  | handle one message: parse, update, feed MLAT |
| `ws_server.py`  | WebSocket receivers connect to + read APIs |
| `mlat/geometry.py` | lat/lon/alt <-> ECEF |
| `mlat/solver.py`   | least-squares multilateration (real math) |
| `mlat/grouping.py` | group one frame across receivers (needs Beast) |

## Run

```
pip install -r requirements.txt
python main.py              # or: uvicorn main:app --host 0.0.0.0 --port 8000
```

Receivers speak the same protocol as `../receiver`.

APIs: `GET /api/aircraft`, `GET /api/receivers`, `GET /api/status`.



