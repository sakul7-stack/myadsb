"""ADS-B receiver client.

Runs next to a receiver (dump1090). Reads SBS lines from port 30003 and forwards
them to the backend over WebSocket. Edit config.json first.
"""

import json
import socket
import sys
import threading
import time

from websocket import WebSocketApp

DEFAULT_CONFIG = {
    "server_ip": "localhost",
    "server_port": 8000,
    "receiver_info": {
        "location": "My Location",
        "latitude": 27.7172,
        "longitude": 85.3240,
        "altitude": 1300,
    },
    "client_id": "ktm-01",
}


class ADSBClient:
    def __init__(self, config_file="config.json"):
        self.config = self._load_config(config_file)
        self.ws = None
        self.connected = False

    def _load_config(self, path):
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError:
            with open(path, "w") as f:
                json.dump(DEFAULT_CONFIG, f, indent=2)
            print(f"Wrote a default {path} — edit it and run again.")
            sys.exit(1)

    def connect_to_server(self):
        """Open the WebSocket and announce this receiver."""
        cfg = self.config
        url = f"ws://{cfg['server_ip']}:{cfg['server_port']}/ws/adsb"

        def on_open(ws):
            self.connected = True
            print("Connected to backend.")
            ws.send(json.dumps({
                "type": "receiver_info",
                "client_id": cfg["client_id"],
                "receiver_info": cfg["receiver_info"],
            }))

        def on_close(ws, *_):
            self.connected = False
            print("Backend connection closed.")

        def on_error(ws, error):
            self.connected = False
            print(f"WebSocket error: {error}")

        self.ws = WebSocketApp(url, on_open=on_open, on_close=on_close, on_error=on_error)
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

    def _send(self, line):
        if self.connected and self.ws:
            self.ws.send(json.dumps({
                "type": "sbs_message",
                "client_id": self.config["client_id"],
                "message": line,
                "timestamp": time.time(),
            }))

    def forward(self, host, port=30003):
        """Stream SBS lines from dump1090 to the backend."""
        if host == "test":
            self._send_test_data()
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        print(f"Reading SBS from {host}:{port}")

        buffer = ""
        while True:
            data = sock.recv(4096).decode("utf-8", errors="ignore")
            if not data:
                break
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line:
                    self._send(line)

    def _send_test_data(self):
        """Loop a few fake messages when there is no real receiver."""
        samples = [
            "MSG,3,1,1,ABCDEF,1,2024/01/01,12:00:00.000,2024/01/01,12:00:00.000,,35000,,,27.72,85.33,,,,,,,0",
            "MSG,3,1,1,123456,1,2024/01/01,12:00:01.000,2024/01/01,12:00:01.000,TEST123,30000,450,180,27.70,85.30,-1200,,,,,,0",
            "MSG,3,1,1,789ABC,1,2024/01/01,12:00:02.000,2024/01/01,12:00:02.000,,28000,,,27.68,85.35,,,,,,,0",
        ]
        print("Test mode: sending fake data.")
        while True:
            for line in samples:
                self._send(line)
            time.sleep(2)


def main():
    client = ADSBClient()
    print(f"Receiver {client.config['client_id']} -> "
          f"{client.config['server_ip']}:{client.config['server_port']}")

    client.connect_to_server()
    time.sleep(2)  # let the socket come up

    host = input("SBS source IP ('test' for fake data) [test]: ").strip() or "test"
    port = 30003
    if host != "test":
        port = int(input("SBS source port [30003]: ").strip() or 30003)

    client.forward(host, port)


if __name__ == "__main__":
    main()
