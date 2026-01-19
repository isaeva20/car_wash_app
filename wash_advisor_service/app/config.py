import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Конфигурация приложения"""
    USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8001")
    WEATHER_SERVICE_URL = os.getenv("WEATHER_SERVICE_URL", "http://weather-service:8002")
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:darya@advisor-db:5432/advisordb"
    )
    PORT = int(os.getenv("PORT", 8003))
    
    MAX_FORECAST_DAYS = 14
    MIN_PRECIPITATION_THRESHOLD = 0.3
    IDEAL_WASH_TEMPERATURE_MIN = 5
    IDEAL_WASH_TEMPERATURE_MAX = 25
    WIND_SPEED_THRESHOLD = 30
    CACHE_RECOMMENDATION_HOURS = 24
    
    WEIGHT_PRECIPITATION = 0.4
    WEIGHT_TEMPERATURE = 0.3
    WEIGHT_WIND = 0.2
    WEIGHT_HUMIDITY = 0.1
    
    @classmethod
    def validate(cls):
        """Проверка конфигурации"""
        missing_vars = []
        
        if not cls.USER_SERVICE_URL:
            missing_vars.append("USER_SERVICE_URL")
        
        if not cls.WEATHER_SERVICE_URL:
            missing_vars.append("WEATHER_SERVICE_URL")
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

settings = Settings()