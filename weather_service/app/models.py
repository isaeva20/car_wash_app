from sqlalchemy import Column, String, Date, DateTime, Float, Integer, ForeignKey, JSON, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import uuid
from app.database import Base
from datetime import datetime

def generate_uuid():
    return str(uuid.uuid4())

class Location(Base):
    __tablename__ = "locations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    city_name = Column(String, nullable=False, index=True)
    country = Column(String, nullable=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    created_at = Column(Date, server_default=func.now())
    
    forecasts = relationship("WeatherForecast", back_populates="location", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Location(id={self.id}, city={self.city_name})>"

class WeatherForecast(Base):
    __tablename__ = "weather_forecasts"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    location_id = Column(String, ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    temperature_min = Column(Float, nullable=True)
    temperature_max = Column(Float, nullable=True)
    temperature_avg = Column(Float, nullable=True)
    precipitation_probability = Column(Float, nullable=True)
    precipitation_amount = Column(Float, nullable=True)
    weather_code = Column(Integer, nullable=True)
    weather_description = Column(String, nullable=True)
    wind_speed = Column(Float, nullable=True)
    humidity = Column(Integer, nullable=True)
    sunrise = Column(String, nullable=True)
    sunset = Column(String, nullable=True)
    raw_data = Column(JSON, nullable=True)
    forecast_source = Column(String, default="weatherapi")
    is_cached = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, onupdate=datetime.now())
    
    location = relationship("Location", back_populates="forecasts")
    
    def __repr__(self):
        return f"<WeatherForecast(date={self.date}, precip={self.precipitation_probability})>"

class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    location = Column(String, nullable=False)
    requested_at = Column(Date, server_default=func.now())
    endpoint = Column(String, nullable=False)
    response_status = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    was_cached = Column(Boolean, default=False)
    error_message = Column(String, nullable=True)
    
    def __repr__(self):
        return f"<ApiRequestLog(location={self.location}, cached={self.was_cached})>"