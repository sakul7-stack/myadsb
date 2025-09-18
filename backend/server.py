# backend/server.py
import socket
import json
import asyncio
import websockets
from math import radians, cos, sin, sqrt, atan2, degrees
import time
import logging
import sqlite3
from datetime import datetime, timedelta
import threading

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Your location (Kathmandu, Nepal)
MY_LAT = 27.6754528
MY_LON = 85.3350065

# ADS-B settings
IP = "192.168.1.3"
PORT = 30003
RECONNECT_DELAY = 5

# Store aircraft data
aircraft_data = {}

# Database for storing historical paths
class PathDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('aircraft_paths.db', check_same_thread=False)
        self.lock = threading.Lock()
        self.setup_database()
    
    def setup_database(self):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS aircraft_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    icao TEXT,
                    timestamp REAL,
                    lat REAL,
                    lon REAL,
                    altitude INTEGER,
                    track INTEGER,
                    ground_speed INTEGER,
                    callsign TEXT
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_icao_timestamp 
                ON aircraft_positions (icao, timestamp)
            ''')
            self.conn.commit()
    
    def store_position(self, aircraft):
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO aircraft_positions 
                (icao, timestamp, lat, lon, altitude, track, ground_speed, callsign)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                aircraft['icao'],
                time.time(),
                aircraft.get('lat', 0),
                aircraft.get('lon', 0),
                aircraft.get('altitude', 0),
                aircraft.get('track', 0),
                aircraft.get('ground_speed', 0),
                aircraft.get('callsign', '')
            ))
            self.conn.commit()
    
    def get_aircraft_path(self, icao, hours=24):
        with self.lock:
            cursor = self.conn.cursor()
            since = time.time() - (hours * 3600)
            cursor.execute('''
                SELECT timestamp, lat, lon, altitude, track, ground_speed
                FROM aircraft_positions 
                WHERE icao = ? AND timestamp > ? AND lat != 0 AND lon != 0
                ORDER BY timestamp
            ''', (icao, since))
            return cursor.fetchall()
    
    def cleanup_old_data(self, days=7):
        with self.lock:
            cursor = self.conn.cursor()
            cutoff = time.time() - (days * 24 * 3600)
            cursor.execute('DELETE FROM aircraft_positions WHERE timestamp < ?', (cutoff,))
            self.conn.commit()
            logger.info(f"Cleaned up positions older than {days} days")

path_db = PathDatabase()

def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points using Haversine formula."""
    try:
        if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
            return 0.0
        R = 6371.0  # Earth radius in km
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return round(R * c, 1)
    except Exception as e:
        logger.debug(f"Haversine calculation error: {e}")
        return 0.0

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing from point 1 to point 2."""
    try:
        if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
            return 0.0
        dlon = radians(lon2 - lon1)
        lat1, lat2 = radians(lat1), radians(lat2)
        y = sin(dlon) * cos(lat2)
        x = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
        bearing = degrees(atan2(y, x))
        return round((bearing + 360) % 360, 1)
    except Exception as e:
        logger.debug(f"Bearing calculation error: {e}")
        return 0.0

def latlon_to_xy(lat, lon):
    """Convert lat/lon to x,y coordinates (km from your position)."""
    try:
        if lat == 0 or lon == 0:
            return 0.0, 0.0
        dx = (lon - MY_LON) * 111 * cos(radians(MY_LAT))
        dy = (lat - MY_LAT) * 111
        return round(dx, 3), round(dy, 3)
    except Exception as e:
        logger.debug(f"Coordinate conversion error: {e}")
        return 0.0, 0.0

# Aircraft registration and type database (simplified)
AIRCRAFT_TYPES = {
    'A320': 'Airbus A320',
    'A319': 'Airbus A319',
    'A321': 'Airbus A321',
    'A330': 'Airbus A330',
    'A340': 'Airbus A340',
    'A350': 'Airbus A350',
    'A380': 'Airbus A380',
    'B737': 'Boeing 737',
    'B738': 'Boeing 737-800',
    'B739': 'Boeing 737-900',
    'B744': 'Boeing 747-400',
    'B748': 'Boeing 747-8',
    'B757': 'Boeing 757',
    'B763': 'Boeing 767-300',
    'B772': 'Boeing 777-200',
    'B773': 'Boeing 777-300',
    'B77W': 'Boeing 777-300ER',
    'B787': 'Boeing 787',
    'B788': 'Boeing 787-8',
    'B789': 'Boeing 787-9',
    'E190': 'Embraer E190',
    'CRJ9': 'Bombardier CRJ-900'
}

class ComprehensiveADSB:
    def __init__(self):
        self.clients = set()
        self.sock = None
        self.message_count = 0
        
        # Start cleanup task
        asyncio.create_task(self.periodic_cleanup())

    async def periodic_cleanup(self):
        """Periodically clean up old data"""
        while True:
            await asyncio.sleep(3600)  # Every hour
            try:
                path_db.cleanup_old_data(days=7)
                await self.cleanup_old_aircraft()
                
                # Reset message count periodically to prevent overflow
                if self.message_count > 1000000:
                    self.message_count = 0
                    logger.info("Reset message counter")
                    
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def connect_adsb(self):
        """Connect to ADS-B receiver with retry logic."""
        while True:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((IP, PORT))
                self.sock.setblocking(False)
                logger.info(f"✓ Connected to ADS-B at {IP}:{PORT}")
                return True
            except Exception as e:
                logger.error(f"✗ ADS-B connection failed: {e}. Retrying in {RECONNECT_DELAY}s...")
                await asyncio.sleep(RECONNECT_DELAY)

    def parse_sbs_message(self, line):
        """Parse SBS message with enhanced validation."""
        try:
            parts = line.strip().split(",")
            if len(parts) < 10 or parts[0] != "MSG":
                return

            message_type = parts[1] if parts[1] else None
            aircraft_id = parts[4] if len(parts) > 4 and parts[4] else None
            hex_ident = parts[5] if len(parts) > 5 and parts[5] else None
            flight_id = parts[6] if len(parts) > 6 and parts[6] else None

            # Skip invalid aircraft IDs
            if not aircraft_id or aircraft_id == "FFFF08" or len(aircraft_id) != 6:
                return

            # Initialize aircraft if new
            if aircraft_id not in aircraft_data:
                aircraft_data[aircraft_id] = {
                    "icao": aircraft_id,
                    "hex_ident": hex_ident or "",
                    "callsign": flight_id or aircraft_id,
                    "altitude": 0,
                    "ground_speed": 0,
                    "track": 0,
                    "lat": 0.0,
                    "lon": 0.0,
                    "vertical_rate": 0,
                    "squawk": "",
                    "alert": False,
                    "emergency": False,
                    "spi": False,
                    "is_on_ground": False,
                    "last_seen": time.time(),
                    "distance_km": 0.0,
                    "bearing": 0.0,
                    "x": 0.0,
                    "y": 0.0,
                    "message_count": 0,
                    "first_seen": time.time(),
                    "aircraft_type": "",
                    "registration": "",
                    "origin": "",
                    "destination": "",
                    "route": [],
                    "has_position": False
                }

            aircraft = aircraft_data[aircraft_id]
            aircraft["last_seen"] = time.time()
            aircraft["message_count"] += 1
            self.message_count += 1

            # Parse different message types
            position_updated = False
            
            if message_type == "1" and len(parts) > 10 and parts[10]:
                # Identification message
                callsign = parts[10].strip()
                if callsign:
                    aircraft["callsign"] = callsign
                    # Try to determine aircraft type from callsign
                    for type_code, type_name in AIRCRAFT_TYPES.items():
                        if type_code in callsign.upper():
                            aircraft["aircraft_type"] = type_name
                            break
                
            elif message_type == "2" and len(parts) > 15:
                # Surface position message
                aircraft["is_on_ground"] = True
                if parts[12]: aircraft["ground_speed"] = max(0, float(parts[12]))
                if parts[13]: aircraft["track"] = float(parts[13]) % 360
                
                if parts[14] and parts[15]:
                    try:
                        new_lat = float(parts[14])
                        new_lon = float(parts[15])
                        if -90 <= new_lat <= 90 and -180 <= new_lon <= 180:
                            aircraft["lat"] = new_lat
                            aircraft["lon"] = new_lon
                            aircraft["has_position"] = True
                            position_updated = True
                    except ValueError:
                        pass
                        
            elif message_type == "3" and len(parts) > 15:
                # Airborne position message
                aircraft["is_on_ground"] = False
                
                if parts[11]:
                    try:
                        altitude_str = ''.join(filter(str.isdigit, parts[11]))
                        if altitude_str:
                            aircraft["altitude"] = int(altitude_str)
                    except ValueError:
                        pass
                        
                if parts[14] and parts[15]:
                    try:
                        new_lat = float(parts[14])
                        new_lon = float(parts[15])
                        if -90 <= new_lat <= 90 and -180 <= new_lon <= 180:
                            aircraft["lat"] = new_lat
                            aircraft["lon"] = new_lon
                            aircraft["has_position"] = True
                            position_updated = True
                    except ValueError:
                        pass
                        
            elif message_type == "4" and len(parts) > 16:
                # Airborne velocity message
                if parts[12]: aircraft["ground_speed"] = max(0, float(parts[12]))
                if parts[13]: aircraft["track"] = float(parts[13]) % 360
                if parts[16]: aircraft["vertical_rate"] = int(parts[16])
                
            elif message_type == "5" and len(parts) > 21:
                # Surveillance altitude message
                if parts[11]:
                    try:
                        altitude_str = ''.join(filter(str.isdigit, parts[11]))
                        if altitude_str:
                            aircraft["altitude"] = int(altitude_str)
                    except ValueError:
                        pass
                        
                aircraft["alert"] = len(parts) > 18 and parts[18] == "1"
                aircraft["emergency"] = len(parts) > 19 and parts[19] == "1"
                aircraft["spi"] = len(parts) > 20 and parts[20] == "1"
                aircraft["is_on_ground"] = len(parts) > 21 and parts[21] == "1"
                
            elif message_type == "6" and len(parts) > 21:
                # Surveillance ID message
                if parts[11]: aircraft["squawk"] = parts[11]
                aircraft["alert"] = len(parts) > 18 and parts[18] == "1"
                aircraft["emergency"] = len(parts) > 19 and parts[19] == "1"
                aircraft["spi"] = len(parts) > 20 and parts[20] == "1"
                aircraft["is_on_ground"] = len(parts) > 21 and parts[21] == "1"

            # Update position calculations if coordinates changed
            if position_updated:
                self._update_position_data(aircraft)
                # Store position in database for path tracking
                if aircraft["lat"] != 0 and aircraft["lon"] != 0:
                    try:
                        path_db.store_position(aircraft)
                    except Exception as e:
                        logger.debug(f"Failed to store position for {aircraft_id}: {e}")

        except Exception as e:
            logger.debug(f"Error parsing SBS message: {line}, Error: {e}")

    def _update_position_data(self, aircraft):
        """Update calculated position data if lat/lon are valid."""
        if aircraft["lat"] != 0 and aircraft["lon"] != 0:
            aircraft["distance_km"] = haversine_distance(
                MY_LAT, MY_LON, aircraft["lat"], aircraft["lon"]
            )
            aircraft["bearing"] = calculate_bearing(
                MY_LAT, MY_LON, aircraft["lat"], aircraft["lon"]
            )
            aircraft["x"], aircraft["y"] = latlon_to_xy(aircraft["lat"], aircraft["lon"])
        else:
            aircraft["distance_km"] = 0.0
            aircraft["bearing"] = 0.0
            aircraft["x"], aircraft["y"] = 0.0, 0.0

    async def read_adsb(self):
        """Read data from ADS-B receiver."""
        if not self.sock:
            return
            
        try:
            data = self.sock.recv(8192).decode(errors="ignore")
            for line in data.strip().split("\n"):
                if line.strip():
                    self.parse_sbs_message(line)
        except BlockingIOError:
            pass
        except Exception as e:
            logger.error(f"Read error: {e}")
            self.sock = None
            await self.connect_adsb()

    async def cleanup_old_aircraft(self):
        """Remove aircraft not seen for more than 300 seconds."""
        current_time = time.time()
        old_aircraft = [
            icao for icao, data in aircraft_data.items()
            if current_time - data["last_seen"] > 300
        ]
        for icao in old_aircraft:
            del aircraft_data[icao]
            if old_aircraft:
                logger.info(f"Removed {len(old_aircraft)} old aircraft")

    async def send_to_clients(self):
        """Send enhanced data to all connected clients."""
        if not self.clients:
            return
            
        await self.cleanup_old_aircraft()
        
        # Prepare aircraft data with additional info
        enhanced_aircraft = []
        for aircraft in aircraft_data.values():
            enhanced = dict(aircraft)
            
            # Add status indicators
            enhanced["status_class"] = self._get_status_class(aircraft)
            enhanced["altitude_class"] = self._get_altitude_class(aircraft)
            
            # Format display values
            enhanced["altitude_display"] = f"{aircraft['altitude']:,}" if aircraft['altitude'] > 0 else "---"
            enhanced["speed_display"] = f"{aircraft['ground_speed']:.0f}" if aircraft['ground_speed'] > 0 else "---"
            enhanced["track_display"] = f"{aircraft['track']:.0f}°" if aircraft['track'] > 0 else "---"
            enhanced["squawk_display"] = aircraft['squawk'] if aircraft['squawk'] else "----"
            
            # Time since last seen
            enhanced["last_seen_seconds"] = time.time() - aircraft["last_seen"]
            
            enhanced_aircraft.append(enhanced)
        
        if enhanced_aircraft or True:  # Always send data, even if empty
            stats = self._calculate_statistics(enhanced_aircraft)
            
            data_to_send = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "total_aircraft": len(enhanced_aircraft),
                "aircraft": enhanced_aircraft,
                "statistics": stats,
                "message_rate": self.message_count
            }
            
            message = json.dumps(data_to_send, separators=(",", ":"))
            
            # Create a copy of the clients set to avoid "set changed size during iteration" error
            clients_copy = self.clients.copy()
            disconnected = set()
            
            for client in clients_copy:
                try:
                    await client.send(message)
                except Exception as e:
                    logger.debug(f"Client send error: {e}")
                    disconnected.add(client)
                    
            # Remove disconnected clients from the original set
            if disconnected:
                self.clients -= disconnected
                logger.info(f"Disconnected {len(disconnected)} clients. Total: {len(self.clients)}")

    def _get_status_class(self, aircraft):
        """Get CSS class for aircraft status."""
        if aircraft.get("emergency"):
            return "emergency"
        elif aircraft.get("alert"):
            return "alert"
        elif aircraft.get("is_on_ground"):
            return "ground"
        else:
            return "airborne"

    def _get_altitude_class(self, aircraft):
        """Get CSS class for altitude display."""
        alt = aircraft.get("altitude", 0)
        if alt > 30000:
            return "altitude-high"
        elif alt > 10000:
            return "altitude-med"
        else:
            return "altitude-low"

    def _calculate_statistics(self, aircraft_list):
        """Calculate enhanced statistics."""
        total = len(aircraft_list)
        with_position = len([a for a in aircraft_list if a.get("has_position", False)])
        airborne = len([a for a in aircraft_list if not a.get("is_on_ground", True)])
        ground = total - airborne
        emergency = len([a for a in aircraft_list if a.get("emergency", False)])
        
        # Altitude distribution
        alt_ranges = {"0-10k": 0, "10k-30k": 0, "30k+": 0}
        for aircraft in aircraft_list:
            alt = aircraft.get("altitude", 0)
            if alt > 30000:
                alt_ranges["30k+"] += 1
            elif alt > 10000:
                alt_ranges["10k-30k"] += 1
            else:
                alt_ranges["0-10k"] += 1
        
        return {
            "total": total,
            "with_position": with_position,
            "airborne": airborne,
            "ground": ground,
            "emergency": emergency,
            "altitude_distribution": alt_ranges
        }

    async def handle_websocket(self, websocket):
        """Handle WebSocket connection - simplified version for compatibility."""
        # For now, treat all connections as aircraft data streams
        self.clients.add(websocket)
        logger.info(f"Client connected. Total: {len(self.clients)}")
        try:
            # Keep connection alive and handle any incoming messages
            async for message in websocket:
                try:
                    # Handle any client requests here if needed
                    data = json.loads(message)
                    if data.get("type") == "get_path" and data.get("icao"):
                        # Handle path request
                        icao = data["icao"].upper()
                        path_data = path_db.get_aircraft_path(icao, hours=24)
                        response = {
                            "type": "path_data",
                            "icao": icao,
                            "path": [
                                {
                                    "timestamp": p[0],
                                    "lat": p[1],
                                    "lon": p[2],
                                    "altitude": p[3],
                                    "track": p[4],
                                    "ground_speed": p[5]
                                }
                                for p in path_data
                            ]
                        }
                        await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    # Ignore invalid JSON messages
                    pass
                except Exception as e:
                    logger.debug(f"Message handling error: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"Client disconnected. Total: {len(self.clients)}")

    async def main_loop(self):
        """Main processing loop."""
        while True:
            await self.read_adsb()
            await self.send_to_clients()
            await asyncio.sleep(0.05)  # 20 Hz update rate

async def main():
    """Start the enhanced ADS-B server."""
    server = ComprehensiveADSB()
    
    if not await server.connect_adsb():
        logger.error("Failed to connect to ADS-B receiver")
        return
    
    # Start WebSocket server - simplified for compatibility
    start_server = websockets.serve(server.handle_websocket, "localhost", 8765)
    logger.info("✓ Enhanced WebSocket server running on ws://localhost:8765")
    logger.info("✓ Connect frontend to ws://localhost:8765")
    
    try:
        await asyncio.gather(
            start_server,
            server.main_loop()
        )
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if server.sock:
            server.sock.close()
        path_db.conn.close()

if __name__ == "__main__":
    asyncio.run(main())