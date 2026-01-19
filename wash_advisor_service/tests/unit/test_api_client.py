import pytest
from unittest.mock import AsyncMock, MagicMock
import httpx

from app.api_client import APIClient


class TestAPIClient:
    """Тесты для API клиента"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Настройка перед каждым тестом"""
        from app.api_client import APIClient
        self.APIClient = APIClient
    
    @pytest.mark.asyncio
    async def test_get_user_info_success(self):
        """Успешное получение информации о пользователе"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "user_id": "test_user",
            "city": "Moscow",
            "country": "Russia",
            "last_wash_date": "2024-01-01",
            "preferred_wash_interval": 7
        }
        
        mock_client.get = AsyncMock(return_value=mock_response)
        
        api_client = APIClient()
        api_client.client = mock_client
        user_info = await api_client.get_user_info("test_user")
        assert user_info is not None
        assert user_info["user_id"] == "test_user"
        assert user_info["city"] == "Moscow"
        mock_client.get.assert_called_once_with(
            "http://test-user-service/api/users/test_user"
        )
    
    @pytest.mark.asyncio
    async def test_get_user_info_not_found(self):
        """Пользователь не найден"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        mock_client.get = AsyncMock(return_value=mock_response)
        
        api_client = APIClient()
        api_client.client = mock_client
        user_info = await api_client.get_user_info("nonexistent_user")
        assert user_info is None
    
    @pytest.mark.asyncio
    async def test_get_user_info_timeout(self):
        """Таймаут при получении информации о пользователе"""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        
        api_client = APIClient()
        api_client.client = mock_client
        user_info = await api_client.get_user_info("test_user")
        assert user_info is None
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_success(self):
        """Успешное получение прогноза погоды"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "location": {"city_name": "Moscow", "country": "Russia"},
            "forecast": [],
            "cached": False
        }
        
        mock_client.get = AsyncMock(return_value=mock_response)
        
        api_client = APIClient()
        api_client.client = mock_client
        weather_data = await api_client.get_weather_forecast("Moscow", 7)
        assert weather_data is not None
        assert weather_data["location"]["city_name"] == "Moscow"
        mock_client.get.assert_called_once_with(
            "http://test-weather-service/api/weather",
            params={"city": "Moscow", "days": 7}
        )
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_max_days(self):
        """Получение прогноза с ограничением максимального количества дней"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"location": {}, "forecast": []}
        
        mock_client.get = AsyncMock(return_value=mock_response)
        
        api_client = APIClient()
        api_client.client = mock_client
        weather_data = await api_client.get_weather_forecast("Moscow", 30)
        
        assert weather_data is not None
        mock_client.get.assert_called_once_with(
            "http://test-weather-service/api/weather",
            params={"city": "Moscow", "days": 14}
        )
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_not_found(self):
        """Прогноз погоды не найден"""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        mock_client.get = AsyncMock(return_value=mock_response)
        
        api_client = APIClient()
        api_client.client = mock_client
        weather_data = await api_client.get_weather_forecast("NonexistentCity", 7)
        assert weather_data is None
    
    @pytest.mark.asyncio
    async def test_check_service_health_all_healthy(self):
        """Проверка доступности сервисов - все здоровы"""
        mock_client = MagicMock()
        
        user_response = MagicMock()
        user_response.status_code = 200
        
        weather_response = MagicMock()
        weather_response.status_code = 200
        
        mock_client.get = AsyncMock(side_effect=[user_response, weather_response])
        
        api_client = APIClient()
        api_client.client = mock_client
        services_status = await api_client.check_service_health()
        assert services_status["user_service"] == True
        assert services_status["weather_service"] == True
    
    @pytest.mark.asyncio
    async def test_check_service_health_user_service_down(self):
        """Проверка доступности сервисов - User Service недоступен"""
        mock_client = MagicMock()
        
        user_response = MagicMock()
        user_response.status_code = 500
        
        weather_response = MagicMock()
        weather_response.status_code = 200
        
        mock_client.get = AsyncMock(side_effect=[user_response, weather_response])
        
        api_client = APIClient()
        api_client.client = mock_client
        
        services_status = await api_client.check_service_health()
        assert services_status["user_service"] == False
        assert services_status["weather_service"] == True
    
    @pytest.mark.asyncio
    async def test_check_service_health_timeout(self):
        """Проверка доступности сервисов - таймаут"""
        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
        
        api_client = APIClient()
        api_client.client = mock_client
        services_status = await api_client.check_service_health()
        assert services_status["user_service"] == False
        assert services_status["weather_service"] == False
    
    @pytest.mark.asyncio
    async def test_close_client(self):
        """Закрытие клиента"""
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        
        api_client = APIClient()
        api_client.client = mock_client
        await api_client.close()
        mock_client.aclose.assert_called_once()