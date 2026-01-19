from sqlalchemy import Column, String, Date, DateTime, Float, Integer, JSON, Boolean, Text
from sqlalchemy.sql import func
import uuid
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class WashRecommendation(Base):
    __tablename__ = "wash_recommendations"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=False, index=True)
    location = Column(String, nullable=False, index=True)
    recommendation_date = Column(Date, nullable=False, index=True)
    temperature = Column(Float, nullable=True)
    precipitation_probability = Column(Float, nullable=True)
    precipitation_amount = Column(Float, nullable=True)
    wind_speed = Column(Float, nullable=True)
    humidity = Column(Integer, nullable=True)
    weather_description = Column(String, nullable=True)
    score = Column(Float, nullable=True)
    is_recommended = Column(Boolean, default=False)
    reason = Column(Text, nullable=True)
    is_rain_expected = Column(Boolean, default=False)
    is_temperature_optimal = Column(Boolean, default=False)
    is_wind_acceptable = Column(Boolean, default=False)
    days_since_last_wash = Column(Integer, nullable=True)
    is_interval_optimal = Column(Boolean, nullable=True)
    forecast_source = Column(String, default="weather-service")
    raw_forecast_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    expires_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<WashRecommendation(user={self.user_id}, date={self.recommendation_date}, score={self.score})>"


class UserContext(Base):
    __tablename__ = "user_context"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, nullable=False, unique=True, index=True)
    city = Column(String, nullable=True)
    country = Column(String, nullable=True)
    last_wash_date = Column(Date, nullable=True)
    preferred_wash_interval = Column(Integer, default=14)
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    def __repr__(self):
        return f"<UserContext(user={self.user_id}, city={self.city})>"