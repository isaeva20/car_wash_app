import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from app.main import app as fastapi_app
from app.models import ApiRequestLog
from app.schemas import LocationCreate
from app.crud import CRUD
from app.database import get_db


@pytest.fixture
def test_app(db):
    """Создание тестового приложения с подменой зависимостей"""
    app = fastapi_app
    async def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    mock_client = MagicMock()
    mock_client.get_forecast = AsyncMock()
    mock_client.parse_forecast_data = MagicMock()
    mock_client.close = AsyncMock()
    app.state.weather_client = mock_client
    
    with patch('app.main.weather_client', mock_client):
        yield app
    app.dependency_overrides.clear()


class TestHealthCheck:
    """Тесты для health check эндпоинта"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, test_app):
        """Успешный health check"""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "weather-service"
            assert "timestamp" in data


class TestWeatherForecast:
    """Тесты для эндпоинтов прогноза погоды"""
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_success(self, test_app, db):
        """Успешное получение прогноза погоды"""
        
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        location = await CRUD.create_location(db, location_data)
        forecast_data = {
            "date": datetime.now().date().isoformat(),
            "temperature_min": -5.0,
            "temperature_max": 2.0,
            "temperature_avg": -1.5,
            "precipitation_probability": 0.3,
            "precipitation_amount": 1.5,
            "weather_code": 1000,
            "weather_description": "Sunny",
            "wind_speed": 10.0,
            "humidity": 75,
            "sunrise": "08:00 AM",
            "sunset": "04:00 PM",
            "raw_data": {"test": "data"}
        }
        
        await CRUD.create_forecasts(db, location.id, [forecast_data])
        test_app.state.weather_client.get_forecast = AsyncMock(return_value={
            "location": {"name": "Moscow", "country": "Russia", "lat": 55.7558, "lon": 37.6176},
            "forecast": {"forecastday": []}
        })
        test_app.state.weather_client.parse_forecast_data.return_value = {
            "location": {
                "city_name": "Moscow",
                "country": "Russia",
                "lat": 55.7558,
                "lon": 37.6176
            },
            "forecast_days": []
        }
        with patch('app.main.weather_client', test_app.state.weather_client):
            async with AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.get("/api/weather", params={"city": location.city_name, "days": 5})
                assert response.status_code == 200, f"Response: {response.text}"
                data = response.json()
                assert data["location"]["city_name"] == location.city_name
                assert "forecast" in data
                assert isinstance(data["forecast"], list)
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_fresh_data(self, test_app, sample_weather_api_response, db):
        """Получение свежих данных от API"""
        test_app.state.weather_client.get_forecast = AsyncMock(return_value=sample_weather_api_response)
        test_app.state.weather_client.parse_forecast_data.return_value = {
            "location": {
                "city_name": "London",
                "country": "UK",
                "lat": 51.5074,
                "lon": -0.1278
            },
            "forecast_days": [
                {
                    "date": "2024-01-20",
                    "temperature_min": 3.0,
                    "temperature_max": 8.0,
                    "temperature_avg": 5.5,
                    "precipitation_probability": 0.4,
                    "precipitation_amount": 2.0,
                    "weather_code": 1003,
                    "weather_description": "Partly cloudy",
                    "wind_speed": 12.0,
                    "humidity": 80,
                    "sunrise": "08:00 AM",
                    "sunset": "04:00 PM"
                }
            ]
        }
        with patch('app.main.weather_client', test_app.state.weather_client):
            async with AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.get("/api/weather", params={"city": "London", "days": 3})
                assert response.status_code == 200, f"Response: {response.text}"
                data = response.json()
                assert data["location"]["city_name"] == "London"
                assert data["cached"] == False
                assert len(data["forecast"]) == 1
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_city_not_found(self, test_app):
        """Город не найден"""
        test_app.state.weather_client.get_forecast = AsyncMock(return_value=None)
        with patch('app.main.weather_client', test_app.state.weather_client):
            async with AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.get("/api/weather", params={"city": "NonexistentCity", "days": 5})
                assert response.status_code in [404, 500], f"Response: {response.text}"
                if response.status_code == 500:
                    data = response.json()
                    assert "detail" in data
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_missing_city_param(self, test_app):
        """Отсутствует параметр city"""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/weather", params={"days": 5})
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_invalid_days(self, test_app):
        """Неверное количество дней"""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/weather", params={"city": "Moscow", "days": 20})
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_get_weather_forecast_api_client_not_initialized(self, test_app):
        """API клиент не инициализирован"""
        original_client = None
        if hasattr(test_app.state, 'weather_client'):
            original_client = test_app.state.weather_client
            del test_app.state.weather_client
        with patch('app.main.weather_client', None):
            async with AsyncClient(app=test_app, base_url="http://test") as client:
                response = await client.get("/api/weather", params={"city": "Moscow", "days": 5})
                assert response.status_code in [500, 503], f"Response: {response.text}"        
        if original_client is not None:
            test_app.state.weather_client = original_client


class TestServiceStats:
    """Тесты для эндпоинтов статистики"""
    
    @pytest.mark.asyncio
    async def test_get_service_stats_success(self, test_app, db):
        """Успешное получение статистики"""
        for i in range(3):
            log = ApiRequestLog(
                location="Moscow",
                endpoint="/api/weather",
                response_status=200,
                response_time_ms=100 + i * 10,
                was_cached=True if i % 2 == 0 else False,
                requested_at=datetime.now() - timedelta(hours=i)  
            )
            db.add(log)
        await db.commit()
        
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/stats", params={"hours": 24})
            assert response.status_code == 200, f"Response: {response.text}"
            data = response.json()
            assert data["status"] == "success"
            assert "data" in data
            assert "total_requests" in data["data"]
            assert "cache_hit_rate" in data["data"]
    
    @pytest.mark.asyncio
    async def test_get_service_stats_custom_hours(self, test_app, db):
        """Получение статистики за кастомный период"""
        log = ApiRequestLog(
            location="London",
            endpoint="/api/weather",
            response_status=200,
            response_time_ms=150,
            was_cached=True,
            requested_at=datetime.now() - timedelta(hours=12)
        )
        db.add(log)
        await db.commit()
        
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/stats", params={"hours": 48})
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["time_period_hours"] == 48
    
    @pytest.mark.asyncio
    async def test_get_service_stats_invalid_hours(self, test_app):
        """Неверный период времени"""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/stats", params={"hours": 200})
            assert response.status_code == 422


class TestErrorHandling:
    """Тесты обработки ошибок"""
    
    @pytest.mark.asyncio
    async def test_invalid_endpoint(self, test_app):
        """Неверный эндпоинт"""
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/nonexistent")
            assert response.status_code == 404