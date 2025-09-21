from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List

Base = declarative_base()

class AircraftPosition(Base):
    __tablename__ = "aircraft_positions"
    
    time = Column(DateTime(timezone=True), primary_key=True, server_default=func.now())
    icao24 = Column(String(6), primary_key=True, index=True)
    callsign = Column(String(8), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Integer, nullable=True)  # feet
    ground_speed = Column(Integer, nullable=True)  # knots
    track = Column(Integer, nullable=True)  # degrees
    vertical_rate = Column(Integer, nullable=True)  # feet/min
    receiver_id = Column(Integer, nullable=False)
    mlat = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<AircraftPosition {self.icao24} at {self.time}>"

class Receiver(Base):
    __tablename__ = "receivers"
    
    id = Column(Integer, primary_key=True)
    station_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)  # meters above sea level
    last_seen = Column(DateTime(timezone=True))
    status = Column(String(20), default="active")
    api_key = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def to_dict(self):
        return {
            "id": self.id,
            "station_id": self.station_id,
            "name": self.name,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "status": self.status,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None
        }

class MLATCalculation(Base):
    __tablename__ = "mlat_calculations"
    
    id = Column(Integer, primary_key=True)
    icao24 = Column(String(6), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    calculated_lat = Column(Float, nullable=True)
    calculated_lon = Column(Float, nullable=True)
    receivers_used = Column(ARRAY(String), nullable=False)
    accuracy_estimate = Column(Float, nullable=True)  # meters
    calculation_time_ms = Column(Integer, nullable=True)