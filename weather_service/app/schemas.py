from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime

class HealthCheck(BaseModel):
    status: str
    service: str
    database: Optional[str] = None
    timestamp: Optional[str] = None

class LocationBase(BaseModel):
    city_name: str
    country: Optional[str] = "Unknown"
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class LocationCreate(LocationBase):
    pass

class LocationInDB(LocationBase):
    id: str
    created_at: date
    
    class Config:
        from_attributes = True

class WeatherDayBase(BaseModel):
    date: date
    temperature_min: Optional[float] = None
    temperature_max: Optional[float] = None
    temperature_avg: Optional[float] = None
    precipitation_probability: Optional[float] = Field(None, ge=0, le=1)
    precipitation_amount: Optional[float] = Field(None, ge=0)
    weather_code: Optional[int] = None
    weather_description: Optional[str] = None
    wind_speed: Optional[float] = None
    humidity: Optional[int] = Field(None, ge=0, le=100)

class WeatherDayCreate(WeatherDayBase):
    location_id: str
    forecast_source: str = "weatherapi"
    raw_data: Optional[Dict[str, Any]] = None

class WeatherDayInDB(WeatherDayBase):
    id: str
    location_id: str
    forecast_source: str
    is_cached: bool = True
    created_at: date
    updated_at: Optional[date] = None
    
    class Config:
        from_attributes = True

class ForecastRequest(BaseModel):
    city: str
    days: int = Field(10, ge=1, le=14, description="Количество дней прогноза (1-14)")
    
    @validator('city')
    def validate_city(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError('Название города должно быть не менее 2 символов')
        return v.strip()

class ForecastResponseDay(WeatherDayBase):
    is_rainy: Optional[bool] = None
    
    @validator('is_rainy', always=True)
    def calculate_is_rainy(cls, v, values):
        if 'precipitation_probability' in values and values['precipitation_probability'] is not None:
            return values['precipitation_probability'] > 0.6
        return None

class ForecastResponse(BaseModel):
    location: LocationInDB
    forecast: List[ForecastResponseDay]
    cached: bool = False
    requested_at: datetime
    source: str

class WeatherError(BaseModel):
    error: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime