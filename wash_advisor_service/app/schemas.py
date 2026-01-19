from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime

class HealthCheck(BaseModel):
    status: str
    service: str
    database: Optional[str] = None
    user_service: Optional[str] = None
    weather_service: Optional[str] = None
    timestamp: Optional[str] = None

class WashRecommendationRequest(BaseModel):
    user_id: str
    days: int = Field(7, ge=1, le=14, description="Количество дней для анализа")
    force_refresh: bool = Field(False, description="Принудительное обновление данных")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or len(v.strip()) < 1:
            raise ValueError('User ID должен быть указан')
        return v.strip()

class UserContextData(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    last_wash_date: Optional[date] = None
    preferred_wash_interval: int = 7

class WashRecommendationDay(BaseModel):
    date: date
    is_recommended: bool
    score: float = Field(..., ge=0, le=100)
    temperature: Optional[float] = None
    precipitation_probability: Optional[float] = None
    wind_speed: Optional[float] = None
    reason: str
    factors: Dict[str, Any]

class WashRecommendationResponse(BaseModel):
    user_id: str
    location: str
    analysis_date: datetime
    days_since_last_wash: Optional[int] = None
    is_interval_optimal: Optional[bool] = None
    best_day: Optional[WashRecommendationDay] = None
    all_days: List[WashRecommendationDay]
    cached: bool = False

class ServiceStats(BaseModel):
    total_recommendations: int
    successful_recommendations: int
    total_users: int
    average_recommendation_score: Optional[float] = None
    cache_hit_rate: Optional[float] = None
    timestamp: datetime

class WashAdvisorError(BaseModel):
    error: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime