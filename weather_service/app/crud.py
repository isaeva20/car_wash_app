from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from datetime import datetime, timedelta
import logging
from typing import Optional, List, Dict, Any

from app.models import Location, WeatherForecast, ApiRequestLog
from app.schemas import LocationCreate
from app.config import settings

logger = logging.getLogger(__name__)

class CRUD:
    """CRUD операции для работы с базой данных"""
    @staticmethod
    async def get_location_by_city(
        session: AsyncSession, 
        city_name: str
    ) -> Optional[Location]:
        """Получить локацию по названию города"""
        try:
            query = select(Location).where(
                Location.city_name.ilike(f"%{city_name}%")
            )
            result = await session.execute(query)
            location = result.scalar_one_or_none()
            return location
        except Exception as e:
            logger.error(f"Error getting location for {city_name}: {str(e)}")
            return None
    
    @staticmethod
    async def get_location_by_id(
        session: AsyncSession, 
        location_id: str
    ) -> Optional[Location]:
        """Получить локацию по ID"""
        try:
            query = select(Location).where(Location.id == location_id)
            result = await session.execute(query)
            location = result.scalar_one_or_none()
            return location
        except Exception as e:
            logger.error(f"Error getting location by ID {location_id}: {str(e)}")
            return None
    
    @staticmethod
    async def create_location(
        session: AsyncSession, 
        location_data: LocationCreate
    ) -> Optional[Location]:
        """Создать новую локацию"""
        try:
            existing = await CRUD.get_location_by_city(
                session, 
                location_data.city_name
            )
            
            if existing:
                logger.info(f"Location {location_data.city_name} already exists")
                return existing
            
            location = Location(
                city_name=location_data.city_name,
                country=location_data.country,
                lat=location_data.lat,
                lon=location_data.lon
            )
            
            session.add(location)
            await session.flush()
            await session.refresh(location)
            
            logger.info(f"Created new location: {location.city_name} (ID: {location.id})")
            return location
            
        except Exception as e:
            logger.error(f"Error creating location: {str(e)}")
            await session.rollback()
            return None

    @staticmethod
    async def get_cached_forecast(
        session: AsyncSession, 
        location_id: str,
        days: int = 10
    ) -> Optional[List[WeatherForecast]]:
        """Получить кэшированный прогноз погоды"""
        try:
            cache_limit = datetime.now() - timedelta(hours=settings.CACHE_TTL_HOURS)
            cache_limit_date = cache_limit.date()
            query = (
                select(WeatherForecast)
                .where(
                    and_(
                        WeatherForecast.location_id == location_id,
                        WeatherForecast.created_at >= cache_limit_date,
                        WeatherForecast.is_cached == True
                    )
                )
                .order_by(WeatherForecast.date.asc())
                .limit(days)
            )
            
            result = await session.execute(query)
            forecasts = result.scalars().all()
            
            if forecasts:
                logger.info(f"Found {len(forecasts)} cached forecasts for location {location_id}")
                return forecasts
            
            logger.debug(f"No cached forecasts found for location {location_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached forecast: {str(e)}")
            return None
    
    @staticmethod
    async def create_forecasts(
        session: AsyncSession,
        location_id: str,
        forecast_days: List[Dict[str, Any]],
        source: str = "weatherapi"
    ) -> List[WeatherForecast]:
        """Создать записи прогноза погоды"""
        forecasts = []
        
        try:
            for day_data in forecast_days:
                date_str = day_data['date']
                try:
                    if isinstance(date_str, str):
                        forecast_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    else:
                        forecast_date = date_str
                except (ValueError, TypeError) as e:
                    logger.error(f'Error parsing date {date_str}: {e}')
                    continue
                existing_query = select(WeatherForecast).where(
                    and_(
                        WeatherForecast.location_id == location_id,
                        WeatherForecast.date == forecast_date
                    )
                )
                existing_result = await session.execute(existing_query)
                existing_forecast = existing_result.scalar_one_or_none()
                
                if existing_forecast:
                    existing_forecast.temperature_min = day_data.get('temperature_min')
                    existing_forecast.temperature_max = day_data.get('temperature_max')
                    existing_forecast.temperature_avg = day_data.get('temperature_avg')
                    existing_forecast.precipitation_probability = day_data.get('precipitation_probability')
                    existing_forecast.precipitation_amount = day_data.get('precipitation_amount')
                    existing_forecast.weather_code = day_data.get('weather_code')
                    existing_forecast.weather_description = day_data.get('weather_description')
                    existing_forecast.wind_speed = day_data.get('wind_speed')
                    existing_forecast.humidity = day_data.get('humidity')
                    existing_forecast.sunrise = day_data.get('sunrise')
                    existing_forecast.sunset = day_data.get('sunset')
                    existing_forecast.raw_data = day_data.get('raw_data')
                    existing_forecast.is_cached = True
                    
                    forecasts.append(existing_forecast)
                    logger.info(f"Updated forecast for {forecast_date}")
                else:
                    forecast = WeatherForecast(
                        location_id=location_id,
                        date=forecast_date,
                        temperature_min=day_data.get('temperature_min'),
                        temperature_max=day_data.get('temperature_max'),
                        temperature_avg=day_data.get('temperature_avg'),
                        precipitation_probability=day_data.get('precipitation_probability'),
                        precipitation_amount=day_data.get('precipitation_amount'),
                        weather_code=day_data.get('weather_code'),
                        weather_description=day_data.get('weather_description'),
                        wind_speed=day_data.get('wind_speed'),
                        humidity=day_data.get('humidity'),
                        sunrise=day_data.get('sunrise'),
                        sunset=day_data.get('sunset'),
                        raw_data=day_data.get('raw_data'),
                        forecast_source=source,
                        is_cached=True
                    )
                    
                    session.add(forecast)
                    forecasts.append(forecast)
                    logger.info(f"Created new forecast for {forecast_date}")
            
            await session.flush()
            logger.info(f"Created/updated {len(forecasts)} forecasts for location {location_id}")
            return forecasts
            
        except Exception as e:
            logger.error(f"Error creating forecasts: {str(e)}")
            await session.rollback()
            return []
    
    @staticmethod
    async def delete_old_forecasts(
        session: AsyncSession,
        location_id: str
    ) -> int:
        """Удалить старые кэшированные прогнозы"""
        try:
            cache_limit = datetime.now() - timedelta(hours=settings.CACHE_TTL_HOURS)
            cache_limit_date = cache_limit.date()
            
            query = delete(WeatherForecast).where(
                and_(
                    WeatherForecast.location_id == location_id,
                    WeatherForecast.created_at < cache_limit_date,
                    WeatherForecast.is_cached == True
                )
            )
            
            result = await session.execute(query)
            deleted_count = result.rowcount
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old cached forecasts for location {location_id}")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting old forecasts: {str(e)}")
            return 0
    
    @staticmethod
    async def log_api_request(
        session: AsyncSession,
        location: str,
        endpoint: str,
        response_status: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        was_cached: bool = False,
        error_message: Optional[str] = None
    ) -> Optional[ApiRequestLog]:
        """Записать лог API запроса"""
        try:
            log = ApiRequestLog(
                location=location,
                endpoint=endpoint,
                response_status=response_status,
                response_time_ms=response_time_ms,
                was_cached=was_cached,
                error_message=error_message
            )
            
            session.add(log)
            await session.flush()
            await session.refresh(log)
            
            logger.debug(f"Logged API request for {location}, cached: {was_cached}")
            return log
            
        except Exception as e:
            logger.error(f"Error logging API request: {str(e)}")
            return None
    
    @staticmethod
    async def get_request_stats(
        session: AsyncSession,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Получить статистику запросов за последние N часов"""
        try:
            time_limit = datetime.now() - timedelta(hours=hours)
            total_query = select(ApiRequestLog).where(
                ApiRequestLog.requested_at >= time_limit
            )
            total_result = await session.execute(total_query)
            total_requests = len(total_result.scalars().all())
            cached_query = select(ApiRequestLog).where(
                and_(
                    ApiRequestLog.requested_at >= time_limit,
                    ApiRequestLog.was_cached == True
                )
            )
            cached_result = await session.execute(cached_query)
            cached_requests = len(cached_result.scalars().all())
            error_query = select(ApiRequestLog).where(
                and_(
                    ApiRequestLog.requested_at >= time_limit,
                    ApiRequestLog.response_status >= 400
                )
            )
            error_result = await session.execute(error_query)
            error_requests = len(error_result.scalars().all())
            
            stats = {
                "total_requests": total_requests,
                "cached_requests": cached_requests,
                "error_requests": error_requests,
                "cache_hit_rate": cached_requests / total_requests if total_requests > 0 else 0,
                "time_period_hours": hours
            }

            logger.info(f"Request stats for last {hours} hours: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting request stats: {str(e)}")
            return {}