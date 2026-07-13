"""Group one aircraft transmission as heard by several receivers.

MLAT needs the SAME Mode-S frame, seen by >= MLAT_MIN_RECEIVERS, each tagged with
that receiver's precise time of arrival. We collect those hits here and, once
enough receivers report the same frame, hand them to the solver.

STATUS: interface only. This needs Beast-format frames with per-receiver
timestamps. SBS/port-30003 gives decoded messages with no usable timing, so the
matching + timing below is a documented stub. Everything downstream (solver.py)
is ready for real data.
"""

from config import settings
from mlat import solver


class FrameGrouper:
    def __init__(self, min_receivers=None):
        self.min_receivers = min_receivers or settings.MLAT_MIN_RECEIVERS
        # frame_key -> list of (receiver_position_ecef, toa_seconds)
        self._pending = {}

    def add_hit(self, frame_key, receiver_pos, toa_seconds, altitude_m):
        """Record that a receiver heard a frame at a given time of arrival.

        frame_key must be identical across receivers for the same transmission
        (e.g. the raw Mode-S message bytes). altitude_m is the aircraft's own
        barometric altitude from that message. Returns a fix dict once enough
        receivers report the same frame, else None.
        """
        hits = self._pending.setdefault(frame_key, [])
        hits.append((receiver_pos, toa_seconds))

        if len(hits) < self.min_receivers:
            return None

        del self._pending[frame_key]
        result = solver.solve(hits, altitude_m)
        if result is None:
            return None

        (lat, lon, alt), rms = result
        return {
            "latitude": lat,
            "longitude": lon,
            "altitude": alt,
            "receivers_used": len(hits),
            "accuracy_m": rms,
            "mlat": True,
        }

    def drop(self, frame_key):
        """Forget a frame we never gathered enough receivers for."""
        self._pending.pop(frame_key, None)
