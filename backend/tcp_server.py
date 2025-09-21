import asyncio
import logging
import json
from typing import Dict, Set
from datetime import datetime
import weakref

logger = logging.getLogger(__name__)

class ReceiverConnection:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, 
                 addr: tuple, server: 'TCPServer'):
        self.reader = reader
        self.writer = writer
        self.addr = addr
        self.server_ref = weakref.ref(server)
        self.station_id: str = None
        self.authenticated = False
        self.last_message_time = datetime.utcnow()
        self.message_count = 0
        
    async def send_message(self, message: str):
        """Send message to receiver"""
        try:
            self.writer.write(f"{message}\n".encode())
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error sending to {self.addr}: {e}")
            await self.disconnect()
    
    async def disconnect(self):
        """Clean disconnect"""
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass
        
        server = self.server_ref()
        if server and self.station_id:
            server.remove_connection(self.station_id)

class TCPServer:
    def __init__(self, host: str, port: int, message_processor):
        self.host = host
        self.port = port
        self.message_processor = message_processor
        self.connections: Dict[str, ReceiverConnection] = {}
        self.server = None
        
    async def start(self):
        """Start the TCP server"""
        self.server = await asyncio.start_server(
            self.handle_client, self.host, self.port
        )
        logger.info(f"TCP Server started on {self.host}:{self.port}")
        
    async def stop(self):
        """Stop the TCP server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        # Disconnect all clients
        for conn in list(self.connections.values()):
            await conn.disconnect()
            
    async def handle_client(self, reader: asyncio.StreamReader, 
                          writer: asyncio.StreamWriter):
        """Handle new client connection"""
        addr = writer.get_extra_info('peername')
        logger.info(f"New connection from {addr}")
        
        conn = ReceiverConnection(reader, writer, addr, self)
        
        try:
            # Wait for authentication
            auth_data = await self.wait_for_auth(conn)
            if not auth_data:
                logger.warning(f"Authentication failed for {addr}")
                return
                
            conn.station_id = auth_data['station_id']
            conn.authenticated = True
            self.connections[conn.station_id] = conn
            
            logger.info(f"Receiver {conn.station_id} connected from {addr}")
            
            # Send acknowledgment
            await conn.send_message(json.dumps({
                "type": "auth_response",
                "status": "success",
                "message": "Connected successfully"
            }))
            
            # Start receiving messages
            await self.receive_messages(conn)
            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            await conn.disconnect()
            logger.info(f"Connection closed for {addr}")
    
    async def wait_for_auth(self, conn: ReceiverConnection, timeout: int = 30) -> dict:
        """Wait for authentication message"""
        try:
            # Read authentication message
            auth_line = await asyncio.wait_for(
                conn.reader.readline(), timeout=timeout
            )
            auth_data = json.loads(auth_line.decode().strip())
            
            # Validate authentication
            if self.validate_auth(auth_data):
                return auth_data
                
        except (asyncio.TimeoutError, json.JSONDecodeError, KeyError):
            pass
        except Exception as e:
            logger.error(f"Auth error: {e}")
            
        return None
    
    def validate_auth(self, auth_data: dict) -> bool:
        """Validate authentication data"""
        required_fields = ['station_id', 'api_key', 'lat', 'lon']
        
        if not all(field in auth_data for field in required_fields):
            return False
            
        # TODO: Validate API key against database
        # For now, accept any valid format
        return len(auth_data['station_id']) > 0
    
    async def receive_messages(self, conn: ReceiverConnection):
        """Receive and process messages from receiver"""
        buffer = ""
        
        while True:
            try:
                data = await conn.reader.read(4096)
                if not data:
                    break
                    
                buffer += data.decode('utf-8', errors='ignore')
                lines = buffer.split('\n')
                buffer = lines[-1]  # Keep incomplete line in buffer
                
                for line in lines[:-1]:
                    if line.strip():
                        await self.process_message(conn, line.strip())
                        conn.message_count += 1
                        conn.last_message_time = datetime.utcnow()
                        
            except Exception as e:
                logger.error(f"Error receiving from {conn.station_id}: {e}")
                break
    
    async def process_message(self, conn: ReceiverConnection, message: str):
        """Process received message"""
        try:
            # Add receiver info to message
            message_data = {
                'raw_message': message,
                'receiver_id': conn.station_id,
                'timestamp': datetime.utcnow().isoformat(),
                'receiver_addr': conn.addr
            }
            
            # Send to message processor
            await self.message_processor.process(message_data)
            
        except Exception as e:
            logger.error(f"Error processing message from {conn.station_id}: {e}")
    
    def remove_connection(self, station_id: str):
        """Remove connection from active connections"""
        if station_id in self.connections:
            del self.connections[station_id]
    
    def get_connected_receivers(self) -> Dict[str, dict]:
        """Get info about connected receivers"""
        return {
            station_id: {
                'addr': conn.addr,
                'message_count': conn.message_count,
                'last_message': conn.last_message_time.isoformat(),
                'connected_since': conn.last_message_time.isoformat()
            }
            for station_id, conn in self.connections.items()
        }