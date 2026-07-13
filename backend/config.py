try:
    from pydantic_settings import BaseSettings  # pydantic v2
except ImportError:
    from pydantic import BaseSettings           # pydantic v1


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:pass@localhost/adsb_db"
    REDIS_URL: str = "redis://localhost:6379"

    # Network
    WS_HOST: str = "0.0.0.0"
    WS_PORT: int = 8000
    MAX_CONNECTIONS: int = 1000

    AIRCRAFT_TIMEOUT_S: int = 300   # drop aircraft after this many seconds silent
    CLEANUP_INTERVAL_S: int = 30

    # MLAT
    MLAT_MIN_RECEIVERS: int = 4        # need at least this many to solve
    MLAT_MAX_DISTANCE_KM: int = 500    # ignore receivers farther apart than this
    MLAT_ACCURACY_THRESHOLD: float = 100.0  # meters, above this we distrust the fix

    # Security
    JWT_SECRET_KEY: str = "your-secret-key"
    API_RATE_LIMIT: str = "100/minute"

    class Config:
        env_file = ".env"


settings = Settings()
