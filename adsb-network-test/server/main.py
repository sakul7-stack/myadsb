from fastapi import FastAPI, WebSocket, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import psycopg2
import redis
import json
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host="postgres",
        database="adsb_network",
        user="adsb_user",
        password="adsb_password"
    )

# Redis connection
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)


def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS receivers (
            id SERIAL PRIMARY KEY,
            client_id VARCHAR(32) UNIQUE,
            location VARCHAR(255),
            latitude FLOAT,
            longitude FLOAT,
            altitude FLOAT,
            is_online BOOLEAN DEFAULT false,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS aircraft (
            id SERIAL PRIMARY KEY,
            icao24 VARCHAR(6),
            callsign VARCHAR(8),
            altitude FLOAT,
            speed FLOAT,
            track FLOAT,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id SERIAL PRIMARY KEY,
            icao24 VARCHAR(6),
            latitude FLOAT,
            longitude FLOAT,
            altitude FLOAT,
            timestamp TIMESTAMP,
            receiver_id VARCHAR(32)
        )
    """)
    
    conn.commit()
    cur.close()
    conn.close()

@app.on_event("startup")
def startup():
    create_tables()
    print("Database tables created!")

@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        db_ok = cur.fetchone()[0] == 1
        cur.close()
        conn.close()
        
        redis_client.ping()
        redis_ok = True
        
        return {
            "database": "OK" if db_ok else "ERROR",
            "redis": "OK" if redis_ok else "ERROR",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/receivers")
async def get_receivers():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM receivers")
    receivers = cur.fetchall()
    cur.close()
    conn.close()
    
    return {
        "receivers": [
            {
                "id": r[0],
                "client_id": r[1],
                "location": r[2],
                "is_online": r[6],
                "last_seen": r[7].isoformat() if r[7] else None
            } for r in receivers
        ]
    }

@app.websocket("/ws/adsb")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    try:
        data = await websocket.receive_text()
        message = json.loads(data)
        
        if message['type'] == 'receiver_info':
            client_id = message['client_id']
            receiver_info = message['receiver_info']
            
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO receivers (client_id, location, latitude, longitude, altitude, is_online)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (client_id) 
                DO UPDATE SET is_online = %s, last_seen = CURRENT_TIMESTAMP
            """, (client_id, receiver_info['location'], receiver_info['latitude'], 
                  receiver_info['longitude'], receiver_info['altitude'], True, True))
            conn.commit()
            cur.close()
            conn.close()
            
            await websocket.send_text(json.dumps({"status": "connected", "client_id": client_id}))
            
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                if message['type'] == 'sbs_message':
                    print(f"Received SBS data from {client_id}: {message['message']}")
                    redis_key = f"adsb:{client_id}:{datetime.now().timestamp()}"
                    redis_client.setex(redis_key, 300, message['message'])
                    
                    parts = message['message'].split(',')
                    if len(parts) >= 5:
                        icao24 = parts[4].strip()
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO aircraft (icao24, last_seen)
                            VALUES (%s, CURRENT_TIMESTAMP)
                            ON CONFLICT (icao24) 
                            DO UPDATE SET last_seen = CURRENT_TIMESTAMP
                        """, (icao24,))
                        
                        if len(parts) >= 15 and parts[14] and parts[15]:
                            cur.execute("""
                                INSERT INTO positions (icao24, latitude, longitude, altitude, timestamp, receiver_id)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (icao24, float(parts[14]), float(parts[15]), 
                                  float(parts[11]) if parts[11] else None, 
                                  datetime.now(), client_id))
                        
                        conn.commit()
                        cur.close()
                        conn.close()
                        
                    await websocket.send_text(json.dumps({"status": "processed"}))
                    
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
