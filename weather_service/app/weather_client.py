import httpx
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class WeatherAPIClient:
    """Клиент для работы с weatherapi.com"""
    
    def __init__(self):
        self.api_key = os.getenv("WEATHER_API_KEY")
        self.base_url = os.getenv("WEATHER_API_URL", "https://api.weatherapi.com/v1/forecast.json")
        self.client = httpx.AsyncClient(
            timeout=15.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        if not self.api_key:
            logger.warning("WEATHER_API_KEY not configured or using default value")
    
    async def get_forecast(self, city: str, days: int = 10) -> Optional[Dict[str, Any]]:
        """Получить прогноз погоды от weatherapi.com"""
        
        if not self.api_key:
            logger.error("Weather API key not configured")
            return None
        
        logger.info(f"Fetching weather forecast for {city}, {days} days")
        for attempt in range(3):
            try:
                logger.info(f"Attempt {attempt + 1} for {city}")
                
                params = {
                    "key": self.api_key,
                    "q": city,
                    "days": days,
                    "aqi": "no",
                    "alerts": "no",
                    "lang": "ru"
                }
                
                start_time = datetime.now()
                response = await self.client.get(self.base_url, params=params)
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                logger.info(f"Weather API response time: {response_time:.0f}ms, status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    if self._validate_response(data):
                        logger.info(f"Successfully fetched forecast for {city}, {days} days")
                        return data
                    else:
                        logger.warning(f"Invalid response structure for {city}")
                        continue
                
                elif response.status_code == 400:
                    logger.error(f"Bad request for {city}: {response.text}")
                    return None
                
                elif response.status_code == 401:
                    logger.error(f"Invalid API key for weatherapi.com")
                    return None
                
                elif response.status_code == 403:
                    logger.error(f"API key limit exceeded or unauthorized")
                    return None
                
                elif response.status_code == 404:
                    logger.warning(f"City {city} not found in weatherapi.com")
                    return None
                
                else:
                    logger.error(f"Weather API error {response.status_code}: {response.text}")
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    return None
                    
            except httpx.TimeoutException:
                logger.warning(f"Weather API timeout for {city}, attempt {attempt + 1}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
            
            except httpx.RequestError as e:
                logger.error(f"Request error for {city}: {str(e)}")
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
            
            except Exception as e:
                logger.error(f"Unexpected error fetching forecast: {str(e)}")
                return None
        
        logger.warning(f"Failed to fetch forecast for {city} after all attempts")
        return None
    
    def _validate_response(self, data: Dict[str, Any]) -> bool:
        """Валидация структуры ответа от API"""
        required_keys = ['location', 'forecast']
        
        for key in required_keys:
            if key not in data:
                logger.warning(f"Missing required key in response: {key}")
                return False
        
        if 'name' not in data['location']:
            logger.warning("Missing 'name' in location data")
            return False
        
        if 'forecastday' not in data['forecast'] or not data['forecast']['forecastday']:
            logger.warning("Missing or empty 'forecastday' in forecast data")
            return False
        
        return True
    
    def parse_forecast_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Парсинг сырых данных от API в структурированный формат"""
        try:
            location_data = raw_data.get('location', {})
            forecast_days = raw_data.get('forecast', {}).get('forecastday', [])
            
            parsed_days = []
            for day_data in forecast_days:
                date_str = day_data.get('date')
                day_info = day_data.get('day', {})
                astro_info = day_data.get('astro', {})
            
                chance_of_rain = day_info.get('daily_chance_of_rain', 0)
                if isinstance(chance_of_rain, str):
                    try:
                        chance_of_rain = float(chance_of_rain.replace('%', ''))
                    except:
                        chance_of_rain = 0
                
                parsed_day = {
                    'date': date_str,
                    'temperature_min': day_info.get('mintemp_c'),
                    'temperature_max': day_info.get('maxtemp_c'),
                    'temperature_avg': day_info.get('avgtemp_c'),
                    'precipitation_probability': chance_of_rain / 100.0,
                    'precipitation_amount': day_info.get('totalprecip_mm', 0),
                    'weather_code': day_info.get('condition', {}).get('code'),
                    'weather_description': day_info.get('condition', {}).get('text'),
                    'wind_speed': day_info.get('maxwind_kph'),
                    'humidity': day_info.get('avghumidity'),
                    'sunrise': astro_info.get('sunrise'),
                    'sunset': astro_info.get('sunset'),
                    'raw_data': day_data
                }
                
                parsed_days.append(parsed_day)
            
            result = {
                'location': {
                    'city_name': location_data.get('name', 'Unknown'),
                    'country': location_data.get('country', 'Unknown'),
                    'lat': location_data.get('lat', 0),
                    'lon': location_data.get('lon', 0)
                },
                'forecast_days': parsed_days,
                'raw_response': raw_data
            }
            logger.info(f"Parsed forecast data for {result['location']['city_name']}")
            return result
            
        except Exception as e:
            logger.error(f"Error parsing forecast data: {str(e)}")
            return {
                'location': {'city_name': 'Unknown', 'country': 'Unknown', 'lat': 0, 'lon': 0},
                'forecast_days': [],
                'raw_response': raw_data
            }
    
    async def close(self):
        """Закрытие клиента"""
        await self.client.aclose()
        logger.info("Weather API client closed")

_weather_client = None

def get_weather_client() -> WeatherAPIClient:
    """Получение инстанса клиента (синглтон)"""
    global _weather_client
    if _weather_client is None:
        _weather_client = WeatherAPIClient()
    return _weather_client