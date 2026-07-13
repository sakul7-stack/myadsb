"""Message processor: the single place a raw receiver message is handled.

The WebSocket server hands every incoming line here. We parse it, update live
state, and (when timing is available) feed the MLAT grouper. This is the piece
the old tcp_server.py referenced but never had.
"""

import logging

from sbs import parse_sbs
from state import store
from mlat.grouping import FrameGrouper

logger = logging.getLogger(__name__)


class MessageProcessor:
    def __init__(self):
        self.grouper = FrameGrouper()
        self.count = 0

    async def process(self, message_data):
        """Handle one message from a receiver.

        message_data = {
            "raw_message": <SBS line>,
            "receiver_id": <station id>,
            "timestamp": <iso string>,
            ...
        }
        """
        line = message_data.get("raw_message", "")
        station_id = message_data.get("receiver_id")

        parsed = parse_sbs(line)
        if parsed is None:
            return None

        self.count += 1
        plane = store.update(station_id, parsed)

        # MLAT hook: SBS carries no time of arrival, so we cannot group frames
        # yet. Once receivers forward Beast-format frames with timestamps, call
        # self.grouper.add_hit(frame_key, receiver_pos, toa) here and merge any
        # returned fix into `plane`.

        return plane
