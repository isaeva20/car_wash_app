import asyncio
import sys
import os
from typing import  Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import date
import pytest_asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["WEATHER_API_KEY"] = "test-api-key"
os.environ["WEATHER_API_URL"] = "https://api.weatherapi.com/v1/forecast.json"

class MockLogger:
    def get_logger(self, name):
        mock_logger = Mock()
        mock_logger.info = Mock()
        mock_logger.warning = Mock()
        mock_logger.error = Mock()
        mock_logger.debug = Mock()
        mock_logger.exception = Mock()
        return mock_logger

sys.modules['common_logger'] = Mock()
sys.modules['common_logger'].logger = MockLogger()

import sqlalchemy.ext.asyncio
original_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine

def patched_create_async_engine(*args, **kwargs):
    """Пач для create_async_engine, чтобы убрать неподдерживаемые параметры для SQLite"""
    if args and "sqlite" in args[0].lower():
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_pre_ping", None)
    
    return original_create_async_engine(*args, **kwargs)

sqlalchemy.ext.asyncio.create_async_engine = patched_create_async_engine
from app.database import Base
from app.schemas import LocationCreate

@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Создание event loop для тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Тестовый движок базы данных"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture
async def db(engine):
    """Чистая сессия базы данных для каждого теста"""
    Session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    session = Session()
    
    try:
        await session.execute(text("DELETE FROM api_request_logs"))
        await session.execute(text("DELETE FROM weather_forecasts"))
        await session.execute(text("DELETE FROM locations"))
        await session.commit()
        
        yield session
        await session.execute(text("DELETE FROM api_request_logs"))
        await session.execute(text("DELETE FROM weather_forecasts"))
        await session.execute(text("DELETE FROM locations"))
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


@pytest_asyncio.fixture
async def sample_location_data() -> Dict[str, Any]:
    """Пример данных локации"""
    return {
        "city_name": "Moscow",
        "country": "Russia",
        "lat": 55.7558,
        "lon": 37.6176
    }


@pytest_asyncio.fixture
def sample_location_create(sample_location_data) -> LocationCreate:
    """Создание LocationCreate из фикстурных данных"""
    return LocationCreate(**sample_location_data)


@pytest_asyncio.fixture
async def test_location(db, sample_location_create):
    """Создание тестовой локации в БД"""
    from app.crud import CRUD
    
    location = await CRUD.create_location(db, sample_location_create)
    assert location is not None
    return location


@pytest_asyncio.fixture
async def test_forecast(db, test_location):
    """Создание тестового прогноза погоды"""
    from app.crud import CRUD
    
    forecast_data = {
        "date": date.today(),
        "temperature_min": -5.0,
        "temperature_max": 2.0,
        "temperature_avg": -1.5,
        "precipitation_probability": 0.3,
        "precipitation_amount": 1.5,
        "weather_code": 1000,
        "weather_description": "Sunny",
        "wind_speed": 10.0,
        "humidity": 75,
        "sunrise": "08:00 AM",
        "sunset": "04:00 PM",
        "raw_data": {"test": "data"}
    }
    
    forecasts = await CRUD.create_forecasts(
        db, test_location.id, [forecast_data]
    )
    
    assert len(forecasts) > 0
    return forecasts[0]


@pytest_asyncio.fixture
def sample_weather_api_response() -> Dict[str, Any]:
    """Пример ответа от Weather API"""
    return {
        "location": {
            "name": "Moscow",
            "country": "Russia",
            "lat": 55.7558,
            "lon": 37.6176
        },
        "forecast": {
            "forecastday": [
                {
                    "date": "2024-01-20",
                    "day": {
                        "maxtemp_c": 2.0,
                        "mintemp_c": -5.0,
                        "avgtemp_c": -1.5,
                        "daily_chance_of_rain": "30",
                        "totalprecip_mm": 1.5,
                        "condition": {
                            "code": 1000,
                            "text": "Sunny"
                        },
                        "maxwind_kph": 10.0,
                        "avghumidity": 75
                    },
                    "astro": {
                        "sunrise": "08:00 AM",
                        "sunset": "04:00 PM"
                    }
                }
            ]
        }
    }


@pytest_asyncio.fixture
def mock_weather_client():
    """Mock для weather client"""
    mock = MagicMock()
    mock.get_forecast = AsyncMock()
    mock.parse_forecast_data = MagicMock()
    mock.close = AsyncMock()
    return mock


@pytest_asyncio.fixture(autouse=True)
def mock_logger():
    """Mock для логгера"""
    with patch("app.main.logger") as mock_log:
        yield mock_log


@pytest_asyncio.fixture(autouse=True)
def mock_common_logger():
    """Mock для common_logger"""
    with patch("app.main.central_logger") as mock_central_logger:
        mock_logger_instance = Mock()
        mock_logger_instance.info = Mock()
        mock_logger_instance.warning = Mock()
        mock_logger_instance.error = Mock()
        mock_logger_instance.debug = Mock()
        mock_central_logger.get_logger.return_value = mock_logger_instance
        yield mock_central_logger