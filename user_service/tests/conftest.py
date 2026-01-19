import pytest
import asyncio
import sys
import os
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, patch, Mock
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import datetime, timedelta
from jose import jwt
from app.main import app as fastapi_app
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserUpdate
from app.auth import create_access_token


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

class MockLogger:
    def __init__(self):
        self.mock_logger = Mock()
        self.mock_logger.info = Mock()
        self.mock_logger.warning = Mock()
        self.mock_logger.error = Mock()
        self.mock_logger.debug = Mock()
        self.mock_logger.exception = Mock()
    
    def get_logger(self, name):
        return self.mock_logger

mock_logger_instance = MockLogger()

common_logger_module = Mock()
common_logger_module.logger = Mock()
common_logger_module.logger.central_logger = mock_logger_instance

sys.modules['common_logger'] = common_logger_module

import sqlalchemy.ext.asyncio

original_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine

def patched_create_async_engine(*args, **kwargs):
    """Пач для create_async_engine, чтобы убрать неподдерживаемые параметры для SQLite"""
    if args and "sqlite" in args[0].lower():
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_recycle", None)
        kwargs.pop("pool_pre_ping", None)
    elif kwargs.get("url") and "sqlite" in kwargs["url"].lower():
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.pop("pool_recycle", None)
        kwargs.pop("pool_pre_ping", None)
    
    return original_create_async_engine(*args, **kwargs)

sqlalchemy.ext.asyncio.create_async_engine = patched_create_async_engine


@pytest.fixture(scope="session")
def event_loop():
    """Создание event loop для тестов"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Тестовый engine для БД"""
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


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Тестовая сессия БД"""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest.fixture
async def clean_db(test_session):
    """Очистка базы данных между тестами"""
    async with test_session as session:
        await session.execute(text("DELETE FROM users"))
        await session.commit()
    
    yield test_session
    
    async with test_session as session:
        await session.execute(text("DELETE FROM users"))
        await session.commit()


@pytest.fixture
async def db_session(test_session: AsyncSession) -> AsyncSession:
    """Фикстура для подмены зависимости get_db"""
    return test_session


@pytest.fixture
async def override_get_db(clean_db):
    """Фикстура для переопределения зависимости get_db в FastAPI"""
    async def _override_get_db():
        async with clean_db as session:
            yield session
    
    return _override_get_db


@pytest.fixture
def app(override_get_db):
    """Тестовое приложение FastAPI с переопределенной зависимостью БД"""
    fastapi_app.dependency_overrides[get_db] = override_get_db
    
    yield fastapi_app
    
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def mock_db_session():
    """Mock для сессии БД"""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """Пример данных пользователя"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123",
        "city": "Moscow",
        "country": "Russia",
        "preferred_wash_interval": 7
    }


@pytest.fixture
def sample_user_create(sample_user_data) -> UserCreate:
    """Создание UserCreate из фикстурных данных"""
    return UserCreate(**sample_user_data)


@pytest.fixture
def sample_user_update() -> UserUpdate:
    """Пример данных для обновления пользователя"""
    return UserUpdate(
        city="Saint Petersburg",
        country="Russia",
        preferred_wash_interval=10
    )


@pytest.fixture
async def test_user(clean_db, sample_user_data) -> User:
    """Создание тестового пользователя в БД"""
    from app.crud import CRUD
    import uuid
    unique_username = f"testuser_{uuid.uuid4().hex[:8]}"
    unique_email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    
    user_create = UserCreate(
        username=unique_username,
        email=unique_email,
        password=sample_user_data["password"],
        city=sample_user_data["city"],
        country=sample_user_data["country"],
        preferred_wash_interval=sample_user_data["preferred_wash_interval"]
    )
    
    user = await CRUD.create_user(clean_db, user_create)
    
    assert user is not None, f"Failed to create user with username: {unique_username}"
    return user


@pytest.fixture
def valid_token(test_user) -> str:
    """Валидный JWT токен"""
    return create_access_token(
        data={"sub": test_user.username, "user_id": test_user.id}
    )


@pytest.fixture
def expired_token() -> str:
    """Просроченный JWT токен"""
    
    payload = {
        "sub": "expired_user",
        "user_id": "expired_id",
        "exp": datetime.utcnow() - timedelta(minutes=10)
    }
    
    return jwt.encode(payload, "test-secret-key", algorithm="HS256")


@pytest.fixture(autouse=True)
def mock_logger():
    """Mock для логгера"""
    with patch("app.main.logger") as mock_log:
        yield mock_log


@pytest.fixture(autouse=True)
def mock_common_logger():
    """Mock для common_logger во всех тестах"""
    with patch("app.main.central_logger") as mock_central_logger:
        mock_logger_instance = Mock()
        mock_logger_instance.info = Mock()
        mock_logger_instance.warning = Mock()
        mock_logger_instance.error = Mock()
        mock_logger_instance.debug = Mock()
        mock_central_logger.get_logger.return_value = mock_logger_instance
        yield mock_central_logger