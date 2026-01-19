from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import asyncio
import logging
# from common_logger.logger import central_logger
from app.database import get_db, init_db, check_db_connection
from app.schemas import (
    HealthCheck, 
    ForecastResponse,
    LocationInDB,
    LocationCreate,
    ForecastResponseDay
)
from app.crud import CRUD
from app.weather_client import get_weather_client
from app.config import settings

class CentralLogger:
    def get_logger(self, name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        return logger

central_logger = CentralLogger()
logger = central_logger.get_logger("weather_service")

app = FastAPI(
    title="Weather Service",
    description="Сервис прогноза погоды",
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

weather_client = None

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    global weather_client
    logger.info("Starting Weather Service...")
    try:
        await asyncio.sleep(5)
        max_retries = 5
        for i in range(max_retries):
            logger.info(f"Attempting database connection ({i+1}/{max_retries})...")
            connected = await check_db_connection()
            if connected:
                logger.info("Database connection established")
                await init_db()
                logger.info("Weather database initialized")
                break
            else:
                if i < max_retries - 1:
                    logger.warning(f"Waiting 3 seconds before next attempt...")
                    await asyncio.sleep(3)
                else:
                    logger.error("Failed to connect to database after all attempts")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    weather_client = get_weather_client()
    logger.info("Weather API client initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при завершении"""
    global weather_client
    
    if weather_client:
        await weather_client.close()
        logger.info("Weather API client closed")
    
    logger.info("Weather Service stopped")

@app.get("/health", response_model=HealthCheck, tags=["health"])
async def health_check():
    """Проверка здоровья сервиса"""
    db_status = "healthy" if await check_db_connection() else "unhealthy"
    logger.debug(f"Health check - DB: {db_status}")
    
    return HealthCheck(
        status="healthy",
        service="weather-service",
        database=db_status,
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/weather", response_model=ForecastResponse, tags=["weather"])
async def get_weather_forecast(
    city: str = Query(..., description="Название города (например: Moscow, London)"),
    days: int = Query(10, ge=1, le=14, description="Количество дней прогноза (1-14)"),
    session: AsyncSession = Depends(get_db)
):
    """
    Получить прогноз погоды для указанного города.
    
    - **city**: Название города
    - **days**: Количество дней прогноза (максимум 14)
    
    Возвращает прогноз погоды с информацией о кэшировании.
    """
    start_time = datetime.now()
    logger.info(f"Weather forecast request for: {city}, days: {days}")
    
    try:
        cached = False
        location = await CRUD.get_location_by_city(session, city)
        
        if location:
            logger.debug(f"Found existing location: {location.city_name} (ID: {location.id})")
            cached_forecasts = await CRUD.get_cached_forecast(session, location.id, days)
            
            if cached_forecasts and len(cached_forecasts) >= days:
                cached = True
                forecasts_data = cached_forecasts
                logger.info(f"Using cached forecast for {city}")
            else:
                logger.info(f"Cache miss or incomplete for {city}")
        else:
            logger.info(f"New location: {city}")
        
        if not cached:
            logger.info(f"Fetching fresh forecast from API for {city}")
            
            if not weather_client:
                logger.error("Weather API client not initialized")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Weather API client not initialized"
                )
            
            raw_data = await weather_client.get_forecast(city, days)
            
            if not raw_data:
                logger.warning(f"Weather forecast not found for city: {city}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Weather forecast not found for city: {city}"
                )
            
            parsed_data = weather_client.parse_forecast_data(raw_data)
            
            location_data = parsed_data['location']
            location = await CRUD.create_location(
                session, 
                LocationCreate(**location_data)
            )
            
            if not location:
                logger.error(f"Failed to create location for {city}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create location"
                )

            forecasts_data = await CRUD.create_forecasts(
                session,
                location.id,
                parsed_data['forecast_days']
            )

            deleted_count = await CRUD.delete_old_forecasts(session, location.id)
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old cached forecasts for {city}")
                
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        
        location_response = LocationInDB.from_orm(location)
        
        forecast_days = []
        for forecast in forecasts_data[:days]:
            day_data = ForecastResponseDay(
                date=forecast.date,
                temperature_min=forecast.temperature_min,
                temperature_max=forecast.temperature_max,
                temperature_avg=forecast.temperature_avg,
                precipitation_probability=forecast.precipitation_probability,
                precipitation_amount=forecast.precipitation_amount,
                weather_code=forecast.weather_code,
                weather_description=forecast.weather_description,
                wind_speed=forecast.wind_speed,
                humidity=forecast.humidity
            )
            forecast_days.append(day_data)
        
        await CRUD.log_api_request(
            session,
            location=city,
            endpoint="/api/weather",
            response_status=200,
            response_time_ms=int(response_time),
            was_cached=cached
        )
        
        logger.info(f"Forecast for {city} ready, cached: {cached}, time: {response_time:.0f}ms")
        
        return ForecastResponse(
            location=location_response,
            forecast=forecast_days,
            cached=cached,
            requested_at=datetime.now(),
            source="weatherapi.com" if not cached else "cache"
        )
        
    except HTTPException as e:
        await CRUD.log_api_request(
            session,
            location=city,
            endpoint="/api/weather",
            response_status=e.status_code,
            was_cached=False,
            error_message=e.detail
        )
        
        logger.error(f"HTTP error for {city}: {e.detail}")
        raise e
        
    except Exception as e:
        await CRUD.log_api_request(
            session,
            location=city,
            endpoint="/api/weather",
            response_status=500,
            was_cached=False,
            error_message=str(e)
        )
        
        logger.error(f"Unexpected error for {city}: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

@app.get("/api/stats", tags=["stats"])
async def get_service_stats(
    hours: int = Query(24, ge=1, le=168, description="Период в часах (максимум 168 = 7 дней)"),
    session: AsyncSession = Depends(get_db)
):
    """
    Получить статистику работы сервиса.
    
    - **hours**: За какой период получить статистику (в часах)
    """
    try:
        logger.info(f"Getting service stats for last {hours} hours")
        stats = await CRUD.get_request_stats(session, hours)
        logger.info(f"Retrieved service stats: {stats}")
        
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик исключений"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    error_content = {
        "error": "Internal server error",
        "detail": str(exc),
        "timestamp": datetime.now().isoformat()  # Уже строка
    }
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_content
    )

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=True,
        log_level="info"
    )