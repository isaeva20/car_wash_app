import pytest
import pytest_asyncio
import asyncio
import sys
import os
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["USER_SERVICE_URL"] = "http://test-user-service"
os.environ["WEATHER_SERVICE_URL"] = "http://test-weather-service"

sys.modules['common_logger'] = Mock()
sys.modules['common_logger'].logger = Mock()

import sqlalchemy.ext.asyncio

original_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine

def patched_create_async_engine(url, **kwargs):
    """Патч для create_async_engine, который убирает неподдерживаемые параметры для SQLite"""
    if url and "sqlite" in url:
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_pre_ping", None)
    
    if os.getenv("TESTING") == "true" and "postgresql" in url:
        url = "sqlite+aiosqlite:///:memory:"
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_pre_ping", None)
    
    return original_create_async_engine(url, **kwargs)

sqlalchemy.ext.asyncio.create_async_engine = patched_create_async_engine

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
    from app.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest_asyncio.fixture
async def db(engine):
    """Чистая сессия базы данных для каждого теста"""
    async with engine.connect() as connection:
        trans = await connection.begin()
        
        Session = sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        session = Session()
        
        try:
            from app.database import Base
            for table in Base.metadata.sorted_tables:
                await session.execute(text(f"DELETE FROM {table.name}"))
            await session.commit()
            
            yield session
            for table in Base.metadata.sorted_tables:
                await session.execute(text(f"DELETE FROM {table.name}"))
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            await trans.rollback()

@pytest_asyncio.fixture
def sample_user_context_data() -> Dict[str, Any]:
    """Пример данных контекста пользователя"""
    from app.schemas import UserContextData
    
    return UserContextData(
        city="Moscow",
        country="Russia",
        last_wash_date=date.today() - timedelta(days=10),
        preferred_wash_interval=7
    )

@pytest.fixture
def sample_weather_data() -> Dict[str, Any]:
    """Пример данных погоды"""
    return {
        "date": date.today().isoformat(),
        "temperature": 15.0,
        "temperature_min": 10.0,
        "temperature_max": 20.0,
        "temperature_avg": 15.0,
        "precipitation_probability": 0.1,
        "precipitation_amount": 0.5,
        "weather_code": 1000,
        "weather_description": "Sunny",
        "wind_speed": 10.0,
        "humidity": 60,
        "sunrise": "08:00 AM",
        "sunset": "04:00 PM",
        "raw_data": {"test": "data"}
    }


@pytest_asyncio.fixture
def sample_weather_forecast_response() -> Dict[str, Any]:
    """Пример ответа от Weather Service"""
    return {
        "location": {
            "city_name": "Moscow",
            "country": "Russia",
            "lat": 55.7558,
            "lon": 37.6176
        },
        "forecast": [
            {
                "date": date.today().isoformat(),
                "temperature_min": 10.0,
                "temperature_max": 20.0,
                "temperature_avg": 15.0,
                "precipitation_probability": 0.1,
                "precipitation_amount": 0.5,
                "weather_code": 1000,
                "weather_description": "Sunny",
                "wind_speed": 10.0,
                "humidity": 60
            },
            {
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "temperature_min": 8.0,
                "temperature_max": 18.0,
                "temperature_avg": 13.0,
                "precipitation_probability": 0.8,
                "precipitation_amount": 5.0,
                "weather_code": 1003,
                "weather_description": "Rainy",
                "wind_speed": 15.0,
                "humidity": 85
            }
        ],
        "cached": False,
        "source": "weatherapi.com"
    }


@pytest_asyncio.fixture
def sample_user_info() -> Dict[str, Any]:
    """Пример информации о пользователе"""
    return {
        "user_id": "test_user_123",
        "city": "Moscow",
        "country": "Russia",
        "last_wash_date": (date.today() - timedelta(days=10)).isoformat(),
        "preferred_wash_interval": 7
    }


@pytest_asyncio.fixture
async def test_user_context(db, sample_user_info):
    """Создание тестового контекста пользователя"""
    from app.schemas import UserContextData
    from app.crud import CRUD
    
    context_data = UserContextData(
        city=sample_user_info["city"],
        country=sample_user_info["country"],
        last_wash_date=date.fromisoformat(sample_user_info["last_wash_date"]),
        preferred_wash_interval=sample_user_info["preferred_wash_interval"]
    )
    
    context = await CRUD.create_or_update_user_context(
        db,
        "test_user_123",
        context_data
    )
    assert context is not None
    
    await db.commit()
    await db.refresh(context)
    
    return context


@pytest_asyncio.fixture
def sample_wash_recommendation_request():
    """Пример запроса на рекомендацию"""
    from app.schemas import WashRecommendationRequest
    
    return WashRecommendationRequest(
        user_id="test_user_123",
        days=7,
        force_refresh=False
    )


@pytest_asyncio.fixture
def mock_api_client():
    """Mock для API клиента"""
    mock = MagicMock()
    mock.get_user_info = AsyncMock()
    mock.get_weather_forecast = AsyncMock()
    mock.check_service_health = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest_asyncio.fixture
def mock_main_logger():
    """Mock для логгера в app.main"""
    with patch("app.main.logger") as mock_log:
        yield mock_log


@pytest_asyncio.fixture
def mock_advisor_logger():
    """Mock для логгера в app.advisor"""
    with patch("app.advisor.logger") as mock_log:
        yield mock_log


@pytest_asyncio.fixture
def mock_crud_logger():
    """Mock для логгера в app.crud"""
    with patch("app.crud.logger") as mock_log:
        yield mock_log


@pytest_asyncio.fixture
def mock_api_client_logger():
    """Mock для логгера в app.api_client"""
    with patch("app.api_client.logger") as mock_log:
        yield mock_log
