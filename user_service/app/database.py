from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:darya@user-db:5432/userdb")

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base() 

async def get_db() -> AsyncSession:
    """Зависимость для получения асинхронной сессии БД"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    """Инициализация БД (создание таблиц)"""
    try:
        async with engine.begin() as conn:
            # await conn.run_sync(Base.metadata.drop_all)  # Раскомментировать для сброса БД
            await conn.run_sync(Base.metadata.create_all)
        print("Database tables created successfully")
        return True
    except Exception as e:
        print(f"Database initialization error {e}")
        return False

async def check_db_connection():
    """Проверка подключения к БД"""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            await conn.commit()
            return True
    except Exception as e:
        print(f"Database connection error: {e}")
        print(f"   DATABASE_URL: {DATABASE_URL}")
        print(f"   Engine: {engine}")
        return False