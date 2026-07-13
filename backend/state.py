"""In-memory store of current aircraft and connected receivers.

This holds live state only. Long-term history goes to the database (models.py).
Not thread-safe by design: drive it from one asyncio loop.
"""

import time

from config import settings


class AircraftStore:
    def __init__(self):
        self.aircraft = {}   # icao24 -> merged field dict
        self.receivers = {}  # station_id -> {"last_seen", "message_count", ...}

    def receiver_online(self, station_id, info):
        rec = self.receivers.setdefault(station_id, {"message_count": 0})
        rec.update(info)
        rec["last_seen"] = time.time()

    def receiver_offline(self, station_id):
        self.receivers.pop(station_id, None)

    def update(self, station_id, parsed):
        """Merge one parsed SBS message from a given receiver."""
        icao = parsed["icao24"]
        now = time.time()

        plane = self.aircraft.get(icao)
        if plane is None:
            plane = self.aircraft[icao] = {"icao24": icao, "receivers": {}}

        for key, value in parsed.items():
            plane[key] = value
        plane["last_seen"] = now

        # Track which receivers hear this aircraft — MLAT needs it.
        plane["receivers"][station_id] = now

        rec = self.receivers.get(station_id)
        if rec is not None:
            rec["message_count"] = rec.get("message_count", 0) + 1
            rec["last_seen"] = now

        return plane

    def cleanup(self):
        """Drop aircraft and receivers we have not heard from in a while."""
        now = time.time()
        timeout = settings.AIRCRAFT_TIMEOUT_S

        stale = [i for i, p in self.aircraft.items() if now - p["last_seen"] > timeout]
        for icao in stale:
            del self.aircraft[icao]

        gone = [s for s, r in self.receivers.items() if now - r["last_seen"] > timeout]
        for station in gone:
            del self.receivers[station]

        return len(stale), len(gone)

    def snapshot(self):
        """Copy of current aircraft, safe to serialize and send to clients."""
        return {icao: dict(plane) for icao, plane in self.aircraft.items()}


store = AircraftStore()
