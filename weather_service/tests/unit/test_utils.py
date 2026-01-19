import pytest
from datetime import date, datetime
from pydantic import ValidationError

from app.schemas import (
    HealthCheck,
    LocationCreate,
    LocationInDB,
    ForecastRequest,
    ForecastResponseDay,
    WeatherError
)


class TestSchemas:
    """Тесты для Pydantic схем"""
    
    def test_health_check_valid(self):
        """Валидные данные для health check"""
        health = HealthCheck(
            status="healthy",
            service="weather-service",
            database="healthy",
            timestamp="2024-01-19T12:00:00"
        )
        assert health.status == "healthy"
        assert health.service == "weather-service"
        assert health.database == "healthy"
    
    def test_location_create_valid(self):
        """Валидные данные для создания локации"""
        location = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        assert location.city_name == "Moscow"
        assert location.lat == 55.7558
        assert location.lon == 37.6176
    
    def test_location_create_invalid_coordinates(self):
        """Невалидные координаты"""
        with pytest.raises(ValidationError):
            LocationCreate(
                city_name="Moscow",
                lat=100.0,
                lon=37.6176
            )
        
        with pytest.raises(ValidationError):
            LocationCreate(
                city_name="Moscow",
                lat=55.7558,
                lon=200.0
            )
    
    def test_location_in_db(self):
        """Схема LocationInDB"""
        location = LocationInDB(
            id="123",
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176,
            created_at=date.today()
        )
        assert location.id == "123"
        assert location.created_at == date.today()
    
    def test_forecast_request_valid(self):
        """Валидный запрос прогноза"""
        request = ForecastRequest(
            city="Moscow",
            days=10
        )
        assert request.city == "Moscow"
        assert request.days == 10
    
    def test_forecast_request_invalid_city(self):
        """Невалидный город"""
        with pytest.raises(ValidationError):
            ForecastRequest(city="", days=10)
    
    def test_forecast_request_invalid_days(self):
        """Невалидное количество дней"""
        with pytest.raises(ValidationError):
            ForecastRequest(city="Moscow", days=0)
        
        with pytest.raises(ValidationError):
            ForecastRequest(city="Moscow", days=15)
    
    def test_forecast_response_day_valid(self):
        """Валидный день прогноза"""
        day = ForecastResponseDay(
            date=date.today(),
            temperature_min=-5.0,
            temperature_max=2.0,
            temperature_avg=-1.5,
            precipitation_probability=0.3,
            precipitation_amount=1.5,
            weather_code=1000,
            weather_description="Sunny",
            wind_speed=10.0,
            humidity=75
        )
        assert day.date == date.today()
        assert day.temperature_avg == -1.5
        assert day.is_rainy == False
    
    def test_forecast_response_day_rainy(self):
        """Дождливый день"""
        day = ForecastResponseDay(
            date=date.today(),
            precipitation_probability=0.7
        )
        assert day.is_rainy == True
    
    def test_forecast_response_day_invalid_humidity(self):
        """Невалидная влажность"""
        with pytest.raises(ValidationError):
            ForecastResponseDay(
                date=date.today(),
                humidity=150
            )
    
    def test_weather_error(self):
        """Схема ошибки"""
        error = WeatherError(
            error="Internal server error",
            details={"exception": "Database error"},
            timestamp=datetime.now()
        )
        assert error.error == "Internal server error"
        assert "exception" in error.details