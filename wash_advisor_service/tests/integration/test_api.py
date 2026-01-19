import pytest
from fastapi.testclient import TestClient
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
from app.crud import CRUD
from datetime import date
from app.database import get_db

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.main import app as fastapi_app


@pytest.fixture
def mock_api_client():
    """Mock для API клиента"""
    mock = MagicMock()
    mock.get_user_info = AsyncMock()
    mock.get_weather_forecast = AsyncMock()
    mock.check_service_health = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def test_app(db, mock_api_client):
    """Создание тестового приложения с подменой зависимостей"""
    app = fastapi_app

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.state.api_client = mock_api_client
    with patch("app.main.api_client", mock_api_client):
        yield app


@pytest.fixture
def client(test_app):
    """Тестовый клиент для запросов к API"""
    return TestClient(test_app)


class TestHealthCheck:
    """Тесты для эндпоинта проверки здоровья"""

    def test_health_check_success(self, client, mock_api_client):
        """Успешная проверка здоровья сервиса"""
        mock_api_client.check_service_health.return_value = {
            "user_service": "healthy",
            "weather_service": "healthy"
        }
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["user_service"] == "healthy"
        assert data["weather_service"] == "healthy"
        assert "timestamp" in data
        assert "database" in data

class TestWashRecommendations:
    """Тесты для эндпоинта рекомендаций по мойке"""

    def test_get_wash_recommendation_success(self, client, mock_api_client):
        """Успешное получение рекомендации"""
        user_info = {
            "user_id": "test_user_123",
            "city": "Moscow",
            "country": "Russia",
            "last_wash_date": (date.today() - timedelta(days=10)).isoformat(),
            "preferred_wash_interval": 7
        }

        weather_forecast = {
            "location": {"city_name": "Moscow", "country": "Russia"},
            "forecast": [
                {
                    "date": date.today().isoformat(),
                    "temperature_avg": 18.0,
                    "precipitation_probability": 0.1,
                    "precipitation_amount": 0.5,
                    "weather_description": "Sunny",
                    "wind_speed": 10.0,
                    "humidity": 60
                }
            ]
        }

        mock_api_client.get_user_info.return_value = user_info
        mock_api_client.get_weather_forecast.return_value = weather_forecast
        response = client.post("/api/recommendations", json={
            "user_id": "test_user_123",
            "days": 7,
            "force_refresh": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "test_user_123"
        assert data["location"] == "Moscow"
        assert "analysis_date" in data

    def test_get_wash_recommendation_user_not_found(self, client, mock_api_client):
        """Получение рекомендации для несуществующего пользователя"""
        mock_api_client.get_user_info.return_value = None
        response = client.post("/api/recommendations", json={
            "user_id": "non_existent_user",
            "days": 7,
            "force_refresh": False
        })
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_get_wash_recommendation_user_missing_city(self, client, mock_api_client):
        """Получение рекомендации для пользователя без указанного города"""
        user_info = {
            "user_id": "test_user_123",
            "city": None,
            "country": "Russia",
            "last_wash_date": (date.today() - timedelta(days=10)).isoformat(),
            "preferred_wash_interval": 7
        }

        mock_api_client.get_user_info.return_value = user_info
        response = client.post("/api/recommendations", json={
            "user_id": "test_user_123",
            "days": 7,
            "force_refresh": False
        })
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "city" in data["detail"].lower()

    def test_get_wash_recommendation_weather_not_found(self, client, mock_api_client):
        """Получение рекомендации при отсутствии данных о погоде"""
        user_info = {
            "user_id": "test_user_123",
            "city": "Moscow",
            "country": "Russia",
            "last_wash_date": (date.today() - timedelta(days=10)).isoformat(),
            "preferred_wash_interval": 7
        }

        mock_api_client.get_user_info.return_value = user_info
        mock_api_client.get_weather_forecast.return_value = None
        response = client.post("/api/recommendations", json={
            "user_id": "test_user_123",
            "days": 7,
            "force_refresh": False
        })
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "weather" in data["detail"].lower()

    def test_get_wash_recommendation_with_cached_data(self, client, mock_api_client, db):
        """Получение рекомендации с кэшированными данными"""
        weather_data = {
            "temperature": 20.0,
            "precipitation_probability": 0.1,
            "precipitation_amount": 0.5,
            "wind_speed": 10.0,
            "humidity": 60,
            "weather_description": "Sunny",
            "raw_data": {"test": "data"}
        }

        analysis_results = {
            "is_recommended": True,
            "score": 85.0,
            "reason": "Отличные условия",
            "is_rain_expected": False,
            "is_temperature_optimal": True,
            "is_wind_acceptable": True
        }
        
        async def create_test_data():
            recommendation = await CRUD.create_recommendation(
                db,
                "cached_user",
                "Moscow",
                date.today(),
                weather_data,
                analysis_results,
                {"days_since_last_wash": 10, "is_interval_optimal": True}
            )
            await db.commit()
            return recommendation

        user_info = {
            "user_id": "cached_user",
            "city": "Moscow",
            "country": "Russia",
            "last_wash_date": (date.today() - timedelta(days=10)).isoformat(),
            "preferred_wash_interval": 7
        }

        mock_api_client.get_user_info.return_value = user_info

        response = client.post("/api/recommendations", json={
            "user_id": "cached_user",
            "days": 7,
            "force_refresh": False
        })
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] == True
        assert data["user_id"] == "cached_user"
        assert data["location"] == "Moscow"
        assert "best_day" in data
        assert "all_days" in data
        mock_api_client.get_weather_forecast.assert_not_called()

    def test_get_wash_recommendation_force_refresh(self, client, mock_api_client, db):
        """Принудительное обновление рекомендации"""
        user_info = {
            "user_id": "test_user_123",
            "city": "Moscow",
            "country": "Russia",
            "last_wash_date": (date.today() - timedelta(days=10)).isoformat(),
            "preferred_wash_interval": 7
        }

        weather_forecast = {
            "location": {"city_name": "Moscow", "country": "Russia"},
            "forecast": [
                {
                    "date": date.today().isoformat(),
                    "temperature_avg": 18.0,
                    "precipitation_probability": 0.1,
                    "precipitation_amount": 0.5,
                    "weather_description": "Sunny",
                    "wind_speed": 10.0,
                    "humidity": 60
                }
            ]
        }

        mock_api_client.get_user_info.return_value = user_info
        mock_api_client.get_weather_forecast.return_value = weather_forecast
        response = client.post("/api/recommendations", json={
            "user_id": "test_user_123",
            "days": 7,
            "force_refresh": True
        })
        assert response.status_code == 200
        data = response.json()
        assert data["cached"] == False


class TestErrorHandling:
    """Тесты обработки ошибок"""

    def test_invalid_endpoint(self, client):
        """Запрос к несуществующему эндпоинту"""
        response = client.get("/invalid-endpoint")
        assert response.status_code == 404
        assert response.json()["detail"] == "Not Found"

    def test_invalid_request_body(self, client):
        """Запрос с некорректным телом"""
        response = client.post("/api/recommendations", json={
            "user_id": 123,
            "days": 7
        })
        assert response.status_code == 422

    def test_invalid_days_parameter(self, client):
        """Запрос с некорректным параметром days"""
        response = client.post("/api/recommendations", json={
            "user_id": "test_user",
            "days": 0
        })
        assert response.status_code == 422