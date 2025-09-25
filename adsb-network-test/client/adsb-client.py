
import socket
import json
import time
import threading
from websocket import WebSocketApp
import sys
import os

class ADSBClient:
    def __init__(self, config_file='config.json'):
        self.load_config(config_file)
        self.ws = None
        self.connected = False
        
    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            self.server_ip = config['server_ip']
            self.server_port = config['server_port']
            self.receiver_info = config['receiver_info']
            self.client_id = config['client_id']
            
        except Exception as e:
            print(f"Error loading config: {e}")
            # Create default config
            self.create_default_config()
            sys.exit(1)
    
    def create_default_config(self):
        config = {
            "server_ip": "localhost",
            "server_port": 8000,
            "receiver_info": {
                "location": "Test Location",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "altitude": 10
            },
            "client_id": "test_client_001"
        }
        
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        print("Created default config.json. Please edit it with your settings.")
    
    def connect_to_server(self):
        """Connect to ADSB server via WebSocket"""
        ws_url = f"ws://{self.server_ip}:{self.server_port}/ws/adsb"
        
        def on_message(ws, message):
            print(f"Received: {message}")
            
        def on_error(ws, error):
            print(f"WebSocket error: {error}")
            self.connected = False
            
        def on_close(ws, close_status_code, close_msg):
            print("WebSocket connection closed")
            self.connected = False
            
        def on_open(ws):
            print("WebSocket connection established")
            self.connected = True
            
            ws.send(json.dumps({
                'type': 'receiver_info',
                'client_id': self.client_id,
                'receiver_info': self.receiver_info
            }))
        
        self.ws = WebSocketApp(ws_url,
                             on_message=on_message,
                             on_error=on_error,
                             on_close=on_close,
                             on_open=on_open)
        
        # Run WebSocket in separate thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
    
    def forward_sbs_data(self, host, port=30003):
        """Forward SBS data from dump1090 to server"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))
            print(f"Connected to SBS source at {host}:{port}")
            
            # If no real dump1090, simulate some test data
            if host == "test":
                self.send_test_data()
                return
            
            while True:
                try:
                    data = sock.recv(4096).decode('utf-8')
                    if data:
                        lines = data.strip().split('\n')
                        for line in lines:
                            if line and self.connected and self.ws:
                                # Send SBS message to server
                                message = {
                                    'type': 'sbs_message',
                                    'client_id': self.client_id,
                                    'message': line.strip(),
                                    'timestamp': time.time()
                                }
                                self.ws.send(json.dumps(message))
                                print(f"Sent: {line.strip()}")
                    time.sleep(1)
                except socket.timeout:
                    print("Socket timeout, reconnecting...")
                    break
                except Exception as e:
                    print(f"Error reading socket: {e}")
                    break
                    
        except Exception as e:
            print(f"Error connecting to SBS source: {e}")
            # If connection fails, try test mode
            print("Trying test mode with simulated data...")
            self.send_test_data()
    
    def send_test_data(self):
        """Send test ADS-B data for demonstration"""
        test_messages = [
            "MSG,3,1,1,ABCDEF,1,2024/01/01,12:00:00.000,2024/01/01,12:00:00.000,,35000,,,40.7128,-74.0060,,,,",
            "MSG,3,1,1,123456,1,2024/01/01,12:00:01.000,2024/01/01,12:00:01.000,TEST123,30000,450,180,,,-1200,,,",
            "MSG,3,1,1,789ABC,1,2024/01/01,12:00:02.000,2024/01/01,12:00:02.000,,28000,,,,,,,,"
        ]
        
        while True:
            for message in test_messages:
                if self.connected and self.ws:
                    msg = {
                        'type': 'sbs_message',
                        'client_id': self.client_id,
                        'message': message,
                        'timestamp': time.time()
                    }
                    self.ws.send(json.dumps(msg))
                    print(f"Sent test data: {message}")
                time.sleep(5)

def main():
    client = ADSBClient()
    
    print("ADSB Client Starting...")
    print(f"Server: {client.server_ip}:{client.server_port}")
    print(f"Client ID: {client.client_id}")
    
   
    client.connect_to_server()
    
   
    time.sleep(2)
    
    # Get SBS source info
    sbs_host = input("Enter SBS source IP (or 'test' for simulated data, default: test): ") or "test"
    
    if sbs_host != "test":
        sbs_port = int(input("Enter SBS source port (default: 30003): ") or 30003)
    else:
        sbs_port = 30003
    
    print("Starting data forwarding...")
    client.forward_sbs_data(sbs_host, sbs_port)

if __name__ == "__main__":
    main()