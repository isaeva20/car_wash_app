import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """Конфигурация приложения"""
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "d73fd6aac4e642639bb125300251012")
    WEATHER_API_URL = os.getenv("WEATHER_API_URL", "https://api.weatherapi.com/v1/forecast.json")
    DATABASE_URL = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:darya@weather-db:5432/weatherdb"
    )
    PORT = int(os.getenv("PORT", 8002))
    CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", 1))
    
    @classmethod
    def validate(cls):
        """Проверка конфигурации"""
        missing_vars = []
        
        if not cls.WEATHER_API_KEY or cls.WEATHER_API_KEY == "d73fd6aac4e642639bb125300251012":
            missing_vars.append("WEATHER_API_KEY")
        
        if not cls.DATABASE_URL:
            missing_vars.append("DATABASE_URL")
        
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

settings = Settings()