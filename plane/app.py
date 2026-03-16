from flask import Flask,jsonify,render_template
import requests
import time
import threading
from datetime import datetime,timedelta
import os
import socket
import json

app = Flask(__name__, static_folder='static')

aircraft_data={}
last_fetch_time=datetime.now()

def parse_line(line):
    fields=line.strip().split(',')
    if len(fields)!=22 or not fields[4]:
        return None
    return fields

def update_aircraft(fields):
    hex_indent=fields[4]
    now=datetime.now()
    if hex_indent not in aircraft_data:
        aircraft_data[hex_indent]={
            'callsign': None, 'altitude': None, 'ground_speed': None, 'track': None,
            'latitude': None, 'longitude': None, 'vertical_rate': None, 'squawk': None,
            'alert': None, 'emergency': None, 'spi': None, 'is_on_ground': None,
            'last_seen': now, 'positions': []
        }

    plane=aircraft_data[hex_indent]
    plane['last_seen']=now

    if fields[10].strip(): plane['callsign'] = fields[10].strip()
    if fields[11]: plane['altitude'] = fields[11]
    if fields[12]: plane['ground_speed'] = fields[12]
    if fields[13]: plane['track'] = fields[13]
    if fields[14]: 
        try: plane['latitude'] = float(fields[14])
        except: pass
    if fields[15]: 
        try: plane['longitude'] = float(fields[15])
        except: pass
    if fields[16]: plane['vertical_rate'] = fields[16]
    if fields[17]: plane['squawk'] = fields[17]
    if fields[18]: plane['alert'] = fields[18]
    if fields[19]: plane['emergency'] = fields[19]
    if fields[20]: plane['spi'] = fields[20]
    if fields[21]: plane['is_on_ground'] = fields[21]

    if plane['latitude'] is not None and plane['longitude'] is not None:
        plane['positions'].append({
            'lat':plane['latitude'],
            'lon':plane['longitude'],
            'alt':plane['altitude'],
            'timestamp':now.isoformat()
        })
        if len(plane['positions'])>700:
            plane['positions'].pop(0)


def fetch_data_loop():
    global last_fetch_time
    host = ''
    port = 30003
    reconnect_delay = 5

    while True:
        sock = None
        try:
            print(f"Connecting to {host}:{port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))
            print("Connected! Streaming data...")

            buffer = ""
            while True:
                data = sock.recv(4096).decode('ascii', errors='ignore')
                if not data:
                    raise ConnectionError("Server closed connection")

                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if not line:
                        continue

                    parsed = parse_line(line)
                    if parsed:
                        update_aircraft(parsed)

                # Cleanup old aircraft every ~10 seconds (adjust as needed)
                now = datetime.now()
                if (now - last_fetch_time).total_seconds() > 10:
                    to_remove = [
                        hex_id for hex_id, plane in list(aircraft_data.items())
                        if now - plane['last_seen'] > timedelta(minutes=2)
                    ]
                    for hex_id in to_remove:
                        del aircraft_data[hex_id]
                    last_fetch_time = now

        except Exception as e:
            print(f"Connection error: {e}")
            if sock:
                try:
                    sock.close()
                except:
                    pass
            time.sleep(reconnect_delay)

threading.Thread(target=fetch_data_loop,daemon=True).start()

@app.route('/api/aircraft')
def get_aircraft():
    # Return copy to avoid mutation during send
    data_copy = {hex_id: {**plane, 'positions': plane['positions'][:]} for hex_id, plane in aircraft_data.items()}
    return jsonify({'aircraft': data_copy, 'last_fetch': last_fetch_time.isoformat()})

@app.route('/api/flags')
def get_flags():
    with open('flags.json','r',encoding='utf-8') as f:
        flags=json.load(f)
    return jsonify(flags)



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/3d')
def threed():
    return render_template('3d.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True,debig=False)
