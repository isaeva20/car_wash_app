import pytest
from unittest.mock import patch, MagicMock
import httpx
from app.weather_client import WeatherAPIClient


class TestWeatherAPIClient:
    """Тесты для Weather API клиента"""
    
    @pytest.fixture
    def weather_client(self):
        """Создание тестового клиента"""
        client = WeatherAPIClient()
        client.api_key = "test-api-key"
        return client
    
    @pytest.mark.asyncio
    async def test_get_forecast_success(self, weather_client, sample_weather_api_response):
        """Успешное получение прогноза"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_weather_api_response
        
        with patch.object(weather_client.client, 'get', return_value=mock_response) as mock_get:
            result = await weather_client.get_forecast("Moscow", 10)
            assert result is not None
            assert "location" in result
            assert "forecast" in result
            mock_get.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_forecast_no_api_key(self):
        """Отсутствие API ключа"""
        client = WeatherAPIClient()
        client.api_key = None
        result = await client.get_forecast("Moscow")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_forecast_city_not_found(self, weather_client):
        """Город не найден"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "City not found"
        
        with patch.object(weather_client.client, 'get', return_value=mock_response):
            result = await weather_client.get_forecast("NonexistentCity")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_forecast_invalid_api_key(self, weather_client):
        """Неверный API ключ"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Invalid API key"
        
        with patch.object(weather_client.client, 'get', return_value=mock_response):
            result = await weather_client.get_forecast("Moscow")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_forecast_timeout(self, weather_client):
        """Таймаут запроса"""
        with patch.object(weather_client.client, 'get', side_effect=httpx.TimeoutException("Request timeout")):
            result = await weather_client.get_forecast("Moscow")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_forecast_retry_logic(self, weather_client, sample_weather_api_response):
        """Логика повторных попыток"""
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = sample_weather_api_response
        
        with patch.object(weather_client.client, 'get') as mock_get:
            mock_get.side_effect = [
                httpx.TimeoutException("First timeout"),
                httpx.TimeoutException("Second timeout"),
                mock_response_success
            ]
            result = await weather_client.get_forecast("Moscow")
            assert result is not None
            assert mock_get.call_count == 3
    
    def test_validate_response_valid(self, weather_client, sample_weather_api_response):
        """Валидация корректного ответа"""
        result = weather_client._validate_response(sample_weather_api_response)
        assert result is True
    
    def test_validate_response_missing_location(self, weather_client):
        """Ответ без location"""
        invalid_response = {"forecast": {"forecastday": []}}
        result = weather_client._validate_response(invalid_response)
        assert result is False
    
    def test_validate_response_empty_forecast(self, weather_client):
        """Ответ с пустым прогнозом"""
        invalid_response = {
            "location": {"name": "Moscow"},
            "forecast": {"forecastday": []}
        }
        result = weather_client._validate_response(invalid_response)
        assert result is False
    
    def test_parse_forecast_data_success(self, weather_client, sample_weather_api_response):
        """Успешный парсинг данных прогноза"""
        result = weather_client.parse_forecast_data(sample_weather_api_response)
        assert result is not None
        assert "location" in result
        assert "forecast_days" in result
        assert len(result["forecast_days"]) == 1
        
        location = result["location"]
        assert location["city_name"] == "Moscow"
        assert location["country"] == "Russia"
        
        forecast_day = result["forecast_days"][0]
        assert forecast_day["date"] == "2024-01-20"
        assert forecast_day["temperature_min"] == -5.0
        assert forecast_day["temperature_max"] == 2.0
        assert forecast_day["precipitation_probability"] == 0.3
    
    def test_parse_forecast_data_invalid(self, weather_client):
        """Парсинг некорректных данных"""
        invalid_data = {"invalid": "structure"}
        result = weather_client.parse_forecast_data(invalid_data)
        assert result is not None
        assert result["location"]["city_name"] == "Unknown"
        assert result["forecast_days"] == []
    
    def test_parse_forecast_data_string_chance_of_rain(self, weather_client):
        """Парсинг строкового значения chance_of_rain"""
        data = {
            "location": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lon": 37.6176},
            "forecast": {
                "forecastday": [{
                    "date": "2024-01-20",
                    "day": {
                        "maxtemp_c": 2.0,
                        "mintemp_c": -5.0,
                        "avgtemp_c": -1.5,
                        "daily_chance_of_rain": "60%",
                        "totalprecip_mm": 1.5,
                        "condition": {"code": 1000, "text": "Sunny"},
                        "maxwind_kph": 10.0,
                        "avghumidity": 75
                    },
                    "astro": {"sunrise": "08:00 AM", "sunset": "04:00 PM"}
                }]
            }
        }
        result = weather_client.parse_forecast_data(data)
        forecast_day = result["forecast_days"][0]
        assert forecast_day["precipitation_probability"] == 0.6
    
    @pytest.mark.asyncio
    async def test_close_client(self, weather_client):
        """Закрытие клиента"""
        with patch.object(weather_client.client, 'aclose') as mock_aclose:
            await weather_client.close()
            mock_aclose.assert_called_once()