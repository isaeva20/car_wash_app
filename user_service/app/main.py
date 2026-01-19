from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from datetime import datetime, date
from typing import List
import logging
# from common_logger.logger import central_logger
from app.database import get_db, init_db, check_db_connection
from app.schemas import (
    HealthCheck,
    UserCreate,
    UserResponse,
    UserUpdate,
    UserLogin,
    Token
)
from app.crud import CRUD
from app.auth import (
    create_access_token,
    get_current_user
)

class CentralLogger:
    def get_logger(self, name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        return logger

central_logger = CentralLogger()
logger = central_logger.get_logger("user_service")

app = FastAPI(
    title="User Service",
    description="Сервис управления пользователями",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.middleware("http")
async def log_requests_middleware(request, call_next):
    logger.debug(f"{request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        logger.debug(f"{request.method} {request.url.path} {response.status_code}")
        return response
    except Exception as exc:
        logger.error(f"{request.method} {request.url.path} ERROR: {str(exc)[:100]}")
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("Starting User Service...")
    try:
        await asyncio.sleep(5)
        max_retries = 5
        for i in range(max_retries):
            logger.info(f"Attempting database connection ({i+1}/{max_retries})...")
            connected = await check_db_connection()
            if connected:
                logger.info("Database connection established")
                await init_db()
                logger.info("User database initialized")
                break
            else:
                if i < max_retries - 1:
                    logger.warning(f"Waiting 3 seconds before next attempt...")
                    await asyncio.sleep(3)
                else:
                    logger.error("Failed to connect to database after all attempts")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("User service stopped")

@app.get("/health", response_model=HealthCheck, tags=["health"])
async def health_check():
    """Health check с проверкой подключения к БД"""
    db_status = "healthy" if await check_db_connection() else "unhealthy"

    logger.info(f"Health check requested - DB status: {db_status}")

    return HealthCheck(
        status="healthy",
        service="user-service",
        database=db_status,
        timestamp=datetime.now().isoformat()
    )

@app.post("/api/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["users"])
async def create_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_db)
):
    """
    Создать нового пользователя.

    - **username**: Имя пользователя (уникальное)
    - **email**: Email (уникальный)
    - **password**: Пароль (мин. 6 символов)
    - **city**: Город
    - **country**: Страна
    - **preferred_wash_interval**: Предпочтительный интервал между мойками (в днях)
    """
    try:
        logger.info(f"Creating new user: {user_data.username}")
        
        user = await CRUD.create_user(session, user_data)
        
        if not user:
            logger.warning(f"User creation failed - username or email exists: {user_data.username}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username or email already exists"
            )
        
        logger.info(f"User created {user.username} (ID: {user.id})")
        return UserResponse.from_orm(user)
        
    except Exception as e:
        logger.error(f"Error creating user {user_data.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )
    
@app.post("/api/auth/login", response_model=Token, tags=["auth"])
async def login(
    login_data: UserLogin,
    session: AsyncSession = Depends(get_db)
):
    """
    Аутентификация пользователя через JSON.
    
    - **username**: Имя пользователя
    - **password**: Пароль
    
    Возвращает JWT токен для доступа к защищенным эндпоинтам.
    """
    try:
        logger.info(f"Login attempt for user: {login_data.username}")
        
        user = await CRUD.authenticate_user(
            session, 
            login_data.username, 
            login_data.password
        )
        
        if not user:
            logger.warning(f"Failed login attempt for user: {login_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        logger.info(f"User logged in: {user.username}")
        return Token(access_token=access_token, token_type="bearer")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error {login_data.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@app.get("/api/users/{user_id}", response_model=UserResponse, tags=["users"])
async def get_user(
    user_id: str,
    session: AsyncSession = Depends(get_db)
):
    """
    Получить информацию о пользователе по ID.
    """
    try:
        logger.info(f"Fetching user: {user_id}")
        
        user = await CRUD.get_user_by_id(session, user_id)
        
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User fetched {user.username}")
        return UserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user {user_id}:  {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user: {str(e)}"
        )

@app.get("/api/users", response_model=List[UserResponse], tags=["users"])
async def get_all_users(
    session: AsyncSession = Depends(get_db)
):
    """
    Получить список всех пользователей.
    """
    try:
        logger.info("Fetching all users from database")
        
        users = await CRUD.get_all_users(session)
        
        logger.info(f"Retrieved {len(users)} users")
        return [UserResponse.from_orm(user) for user in users]
        
    except Exception as e:
        logger.error(f"Error fetching all users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )

@app.put("/api/users/{user_id}", response_model=UserResponse, tags=["users"])
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Обновить информацию о пользователе.
    """
    try:
        if current_user.get("user_id") != user_id:
            logger.warning(f"Unauthorized update attempt by {current_user.get('username')} for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this user"
            )
        
        logger.info(f"Updating user: {user_id}")
        
        user = await CRUD.update_user(session, user_id, user_data)
        
        if not user:
            logger.warning(f"User not found for update: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info(f"User updated {user.username}")
        return UserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@app.put("/api/users/{user_id}/wash-date", response_model=UserResponse, tags=["users"])
async def update_wash_date(
    user_id: str,
    wash_date: date,
    session: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Обновить дату последней мойки пользователя.
    """
    try:
        if current_user.get("user_id") != user_id:
            logger.warning(f"Unauthorized wash date update by {current_user.get('username')} for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this user"
            )
        
        logger.info(f"Updating wash date for user {user_id} to {wash_date}")
        
        success = await CRUD.update_last_wash_date(session, user_id, wash_date)
        
        if not success:
            logger.warning(f"User not found for wash date update: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user = await CRUD.get_user_by_id(session, user_id)
        
        logger.info(f"Wash date updated for {user.username}")
        return UserResponse.from_orm(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating wash date for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update wash date: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик исключений"""
    logger.error(f"Unhandled exception in {request.method} {request.url.path}: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "details": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )