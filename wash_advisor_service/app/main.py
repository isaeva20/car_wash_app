from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime
import asyncio
import logging
# from common_logger.logger import central_logger
from app.database import get_db, init_db, check_db_connection
from app.schemas import (
    HealthCheck, 
    WashRecommendationRequest,
    WashRecommendationResponse,
    WashRecommendationDay,
    UserContextData,
    ServiceStats,
    WashAdvisorError
)
from app.crud import CRUD
from app.api_client import get_api_client
from app.advisor import WashAdvisorLogic
from app.config import settings

class CentralLogger:
    def get_logger(self, name):
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        return logger

central_logger = CentralLogger()
logger = central_logger.get_logger("wash_advisor_service")

app = FastAPI(
    title="Wash Advisor Service",
    description="Сервис рекомендаций по мойке автомобиля на основе погодных условий",
    version="3.0.0",
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

api_client = None

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    global api_client
    logger.info("Starting Wash Advisor Service...")
    try:
        await asyncio.sleep(5)
        max_retries = 5
        for i in range(max_retries):
            logger.info(f"Attempting database connection ({i+1}/{max_retries})...")
            connected = await check_db_connection()
            if connected:
                logger.info("Database connection established")
                await init_db()
                logger.info("Advisor database initialized")
                break
            else:
                if i < max_retries - 1:
                    logger.warning(f"Waiting 3 seconds before next attempt...")
                    await asyncio.sleep(3)
                else:
                    logger.error("Failed to connect to database after all attempts")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
    api_client = get_api_client()
    logger.info("API Client initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Очистка при завершении"""
    global api_client
    
    if api_client:
        await api_client.close()
        logger.info("API Client closed")
    
    logger.info("Wash Advisor Service stopped")

@app.get("/health", response_model=HealthCheck, tags=["health"])
async def health_check():
    """Проверка здоровья сервиса"""

    db_status = "healthy" if await check_db_connection() else "unhealthy"

    services_status = {}
    if api_client:
        services_status = await api_client.check_service_health()

    user_service_status = "healthy" if services_status.get("user_service") else "unhealthy"
    weather_service_status = "healthy" if services_status.get("weather_service") else "unhealthy"

    logger.info(f"Health check - DB: {db_status}, User Service: {user_service_status}, Weather Service: {weather_service_status}")
    
    return HealthCheck(
        status="healthy",
        service="wash-advisor-service",
        database=db_status,
        user_service=user_service_status,
        weather_service=weather_service_status,
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/recommendations", response_model=WashRecommendationResponse, tags=["recommendations"])
async def get_wash_recommendation(
    request: WashRecommendationRequest,
    session: AsyncSession = Depends(get_db)
):
    """
    Получить рекомендацию по мойке автомобиля.
    
    Анализирует погодные условия на указанное количество дней
    и рекомендует лучший день для мойки.
    """
    start_time = datetime.now()
    logger.info(f"Wash recommendation request for user {request.user_id}, days: {request.days}")
    
    try:
        logger.info(f"Fetching user data for {request.user_id} from User Service")
        user_info = await api_client.get_user_info(request.user_id)
        if not user_info:
            logger.warning(f"User {request.user_id} not found in User Service")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {request.user_id} not found"
            )
        
        if 'city' not in user_info:
            logger.error(f"User {request.user_id} data missing city field: {user_info}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User city is not specified"
            )
        
        location = user_info.get('city')
        if not location:
            logger.error(f"User {request.user_id} data missing city field")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User city is not specified"
            )
        
        logger.info(f"Using location from user data: {location}")

        context_data = UserContextData(
            city=user_info.get('city'),
            country=user_info.get('country'),
            last_wash_date=user_info.get('last_wash_date'),
            preferred_wash_interval=user_info.get('preferred_wash_interval', 7)
        )

        user_context = await CRUD.create_or_update_user_context(
            session,
            request.user_id,
            context_data
        )

        context_metrics = {}
        if user_context:
            context_metrics = await CRUD.calculate_user_context(user_context)
            logger.info(f"User context calculated: {context_metrics}")

        cached = False
        cached_rec = None
        if not request.force_refresh:
            cached_rec = await CRUD.get_cached_recommendation(
                session, 
                request.user_id, 
                location,
                request.days
            )
            
            if cached_rec:
                cached = True
                logger.info(f"Using cached recommendation for user {request.user_id}")

        best_day = None
        all_days = []
        
        if not cached:
            logger.info(f"Fetching fresh weather data for {location}")
            weather_data = await api_client.get_weather_forecast(
                location,
                request.days
            )
            if not weather_data:
                logger.warning(f"Weather forecast not available for {location}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Weather forecast not available for {location}"
                )
            
            forecast_days = weather_data.get('forecast', [])
            analyzed_days = []

            logger.info(f"Analyzing {len(forecast_days)} days of weather data")

            for day in forecast_days:
                analysis = WashAdvisorLogic.analyze_weather_day(
                    day, 
                    user_context=context_metrics
                )
                analyzed_days.append(analysis)
            
            best_day_analysis = WashAdvisorLogic.find_best_wash_day(
                analyzed_days, 
                user_context=context_metrics
            )
            
            all_days_analysis = WashAdvisorLogic.generate_all_days_recommendations(analyzed_days)
            
            # Конвертируем analyzed_days в WashRecommendationDay
            for i, day_analysis in enumerate(all_days_analysis):
                day_data = forecast_days[i] if i < len(forecast_days) else {}
                
                wash_day = WashRecommendationDay(
                    date=date.fromisoformat(day_data.get('date', str(day_analysis.date))) if day_data.get('date') else day_analysis.date,
                    is_recommended=day_analysis.is_recommended,
                    score=day_analysis.score,
                    temperature=day_data.get('temperature_avg') or day_data.get('temperature'),
                    precipitation_probability=day_data.get('precipitation_probability'),
                    wind_speed=day_data.get('wind_speed'),
                    reason=day_analysis.reason,
                    factors=day_analysis.factors
                )
                all_days.append(wash_day)
                
                if best_day_analysis and day_analysis.date == best_day_analysis.date:
                    best_day = wash_day
            
            # Создаем рекомендацию в БД если есть лучший день
            if best_day:
                # Находим соответствующие weather данные для best_day
                weather_day_data = next(
                    (day for day in forecast_days if str(day.get('date', '')) == str(best_day.date)),
                    {}
                )
                
                analysis_results = {
                    'is_recommended': best_day.is_recommended,
                    'score': best_day.score,
                    'reason': best_day.reason,
                    'is_rain_expected': best_day.factors.get('is_rain_expected', False),
                    'is_temperature_optimal': best_day.factors.get('is_temperature_optimal', False),
                    'is_wind_acceptable': best_day.factors.get('is_wind_acceptable', False)
                }
                
                await CRUD.create_recommendation(
                    session,
                    request.user_id,
                    location,
                    best_day.date,
                    weather_day_data,
                    analysis_results,
                    context_metrics
                )
        
        else:
            # Используем кэшированные данные
            # Создаем WashRecommendationDay из кэшированной записи
            cached_day = WashRecommendationDay(
                date=cached_rec.recommendation_date,
                is_recommended=cached_rec.is_recommended,
                score=cached_rec.score,
                temperature=cached_rec.temperature,
                precipitation_probability=cached_rec.precipitation_probability,
                wind_speed=cached_rec.wind_speed,
                reason=cached_rec.reason or "",
                factors={
                    'is_rain_expected': cached_rec.is_rain_expected,
                    'is_temperature_optimal': cached_rec.is_temperature_optimal,
                    'is_wind_acceptable': cached_rec.is_wind_acceptable,
                    'humidity': cached_rec.humidity
                }
            )
            
            best_day = cached_day if cached_rec.is_recommended else None
            all_days = [cached_day]
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        
        logger.info(f"Recommendation ready for user {request.user_id}, cached: {cached}, time: {response_time:.0f}ms")
        
        return WashRecommendationResponse(
            user_id=request.user_id,
            location=location,
            analysis_date=datetime.now(),
            days_since_last_wash=context_metrics.get('days_since_last_wash'),
            is_interval_optimal=context_metrics.get('is_interval_optimal'),
            best_day=best_day,
            all_days=all_days,
            cached=cached
        )
        
    except HTTPException as e:
        logger.error(f"HTTP error for user {request.user_id}: {e.detail}")
        raise e
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/api/stats/service", response_model=ServiceStats, tags=["stats"])
async def get_service_stats(
    days: int = Query(30, ge=1, le=365),
    session: AsyncSession = Depends(get_db)
):
    """Получить статистику работы сервиса"""
    try:
        logger.info(f"Getting service stats for last {days} days")
        stats = await CRUD.get_service_stats(session, days)
        logger.info(f"Service stats retrieved: {stats}")
        
        return ServiceStats(**stats)
        
    except Exception as e:
        logger.error(f"Error getting service stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get service stats: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик исключений"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=WashAdvisorError(
            error="Internal server error",
            details={"exception": str(exc)},
            timestamp=datetime.now()
        ).dict()
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