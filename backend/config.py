from pydantic import BaseSettings
from typing import List, Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:pass@localhost/adsb_db"
    REDIS_URL: str = "redis://localhost:6379"
    
    # Network
    TCP_HOST: str = "0.0.0.0"
    TCP_PORT: int = 30003  # Standard SBS port
    UDP_PORT: int = 30004
    MAX_CONNECTIONS: int = 1000
    
    # MLAT Configuration
    MLAT_MIN_RECEIVERS: int = 4  # Minimum receivers for MLAT
    MLAT_MAX_DISTANCE_KM: int = 500  # Max distance between receivers
    MLAT_ACCURACY_THRESHOLD: float = 100.0  # meters
    
    # Security
    JWT_SECRET_KEY: str = "your-secret-key"
    API_RATE_LIMIT: str = "100/minute"
    
    # Performance
    BATCH_SIZE: int = 1000
    CACHE_TTL: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"

settings = Settings()