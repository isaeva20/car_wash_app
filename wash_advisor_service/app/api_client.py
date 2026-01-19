import httpx
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)

class APIClient:
    """Клиент для взаимодействия с другими сервисами"""
    
    def __init__(self):
        self.user_service_url = settings.USER_SERVICE_URL.rstrip('/')
        self.weather_service_url = settings.WEATHER_SERVICE_URL.rstrip('/')
        self.client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        logger.info(f"API Client initialized: UserService={self.user_service_url}, WeatherService={self.weather_service_url}")
    
    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о пользователе"""
        try:
            url = f"{self.user_service_url}/api/users/{user_id}"
            logger.info(f"Fetching user info: {url}")
            
            response = await self.client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully fetched user info for {user_id}: {data}")
                return data
            elif response.status_code == 404:
                logger.warning(f"User {user_id} not found")
                return None
            else:
                logger.error(f"Error fetching user {user_id}: {response.status_code}")
                return None
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching user info for {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching user info for {user_id}: {str(e)}")
            return None
    
    async def get_weather_forecast(self, location: str, days: int = 7) -> Optional[Dict[str, Any]]:
        """Получить прогноз погоды"""
        try:
            url = f"{self.weather_service_url}/api/weather"
            params = {
                "city": location,
                "days": min(days, settings.MAX_FORECAST_DAYS)
            }
            
            logger.info(f"Fetching weather forecast: {url}, params: {params}")
            
            start_time = datetime.now()
            response = await self.client.get(url, params=params)
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Weather API response time: {response_time:.0f}ms, status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Successfully fetched weather forecast for {location}, {days} days")
                return data
            elif response.status_code == 404:
                logger.warning(f"Weather forecast not found for {location}")
                return None
            else:
                logger.error(f"Error fetching weather for {location}: {response.status_code}")
                return None
                
        except httpx.TimeoutException:
            logger.warning(f"Timeout fetching weather forecast for {location}")
            return None
        except Exception as e:
            logger.error(f"Error fetching weather forecast: {str(e)}")
            return None
    
    async def check_service_health(self) -> Dict[str, bool]:
        """Проверить доступность всех сервисов"""
        services = {
            "user_service": False,
            "weather_service": False
        }
        
        try:
            user_health_url = f"{self.user_service_url}/health"
            try:
                user_response = await self.client.get(user_health_url, timeout=5.0)
                services["user_service"] = user_response.status_code == 200
                logger.debug(f"User Service health check: {services['user_service']}")
            except Exception as e:
                logger.warning(f"User Service health check failed: {str(e)}")
                services["user_service"] = False
            
            weather_health_url = f"{self.weather_service_url}/health"
            try:
                weather_response = await self.client.get(weather_health_url, timeout=5.0)
                services["weather_service"] = weather_response.status_code == 200
                logger.info(f"Weather Service health check: {services['weather_service']}")
            except Exception as e:
                logger.warning(f"Weather Service health check failed: {str(e)}")
                services["weather_service"] = False
            
            logger.info(f"Service health check: User={services['user_service']}, Weather={services['weather_service']}")
            return services
            
        except Exception as e:
            logger.error(f"Error checking service health: {str(e)}")
            return services
    
    async def close(self):
        """Закрыть клиент"""
        await self.client.aclose()
        logger.info("API Client closed")

_api_client = None

def get_api_client() -> APIClient:
    """Получить инстанс клиента API"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client