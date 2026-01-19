import pytest
from unittest.mock import patch
from datetime import date, timedelta
from sqlalchemy import select

from app.crud import CRUD
from app.models import WeatherForecast
from app.schemas import LocationCreate


class TestCRUDOperations:
    """Тесты для CRUD операций"""
    
    @pytest.mark.asyncio
    async def test_get_location_by_city_success(self, db):
        """Успешное получение локации по городу"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        result = await CRUD.get_location_by_city(db, location.city_name)
        assert result is not None
        assert result.city_name == location.city_name
        assert result.country == location.country
    
    @pytest.mark.asyncio
    async def test_get_location_by_city_not_found(self, db):
        """Локация не найдена по городу"""
        result = await CRUD.get_location_by_city(db, "NonexistentCity")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_location_by_city_case_insensitive(self, db):
        """Поиск локации регистронезависимый"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        result = await CRUD.get_location_by_city(db, location.city_name.lower())
        assert result is not None
        assert result.city_name == location.city_name
    
    @pytest.mark.asyncio
    async def test_get_location_by_id_success(self, db):
        """Успешное получение локации по ID"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        result = await CRUD.get_location_by_id(db, location.id)
        assert result is not None
        assert result.id == location.id
    
    @pytest.mark.asyncio
    async def test_get_location_by_id_not_found(self, db):
        """Локация не найдена по ID"""
        result = await CRUD.get_location_by_id(db, "00000000-0000-0000-0000-000000000000")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_location_success(self, db):
        """Успешное создание локации"""
        location_data = LocationCreate(
            city_name="Saint Petersburg",
            country="Russia",
            lat=59.9343,
            lon=30.3351
        )
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        assert location.city_name == location_data.city_name
        assert location.country == location_data.country
        assert location.lat == location_data.lat
        assert location.id is not None
    
    @pytest.mark.asyncio
    async def test_create_location_duplicate(self, db):
        """Создание дубликата локации (должно вернуть существующую)"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        first_location = await CRUD.create_location(db, location_data)
        assert first_location is not None
        second_location = await CRUD.create_location(db, location_data)
        assert second_location is not None
        assert second_location.id == first_location.id
    
    @pytest.mark.asyncio
    async def test_get_cached_forecast_success(self, db):
        """Успешное получение кэшированного прогноза"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        forecast_data = {
            "date": date.today(),
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
        forecasts = await CRUD.get_cached_forecast(db, location.id)
        assert forecasts is not None
        assert len(forecasts) > 0
        assert forecasts[0].location_id == location.id
        assert forecasts[0].is_cached == True
    
    @pytest.mark.asyncio
    async def test_get_cached_forecast_empty(self, db):
        """Нет кэшированных прогнозов"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        forecasts = await CRUD.get_cached_forecast(db, location.id)
        assert forecasts is None
    
    @pytest.mark.asyncio
    @patch("app.crud.settings")
    async def test_get_cached_forecast_expired(self, mock_settings, db):
        """Кэшированные прогнозы истекли"""
        mock_settings.CACHE_TTL_HOURS = 1
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        old_forecast = WeatherForecast(
            location_id=location.id,
            date=date.today(),
            temperature_avg=10.0,
            is_cached=True,
            created_at=date.today() - timedelta(days=2)
        )
        db.add(old_forecast)
        await db.commit()
        forecasts = await CRUD.get_cached_forecast(db, location.id)
        assert forecasts is None
    
    @pytest.mark.asyncio
    async def test_create_forecasts_success(self, db):
        """Успешное создание прогнозов"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None
        
        forecast_days = [
            {
                "date": "2024-01-20",
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
        ]
        forecasts = await CRUD.create_forecasts(
            db, location.id, forecast_days
        )
        assert len(forecasts) == 1
        assert forecasts[0].location_id == location.id
        assert forecasts[0].temperature_avg == -1.5
        assert forecasts[0].is_cached == True
    
    @pytest.mark.asyncio
    async def test_create_forecasts_update_existing(self, db):
        """Обновление существующего прогноза"""
        location_data = LocationCreate(
            city_name="Moscow",
            country="Russia",
            lat=55.7558,
            lon=37.6176
        )
        
        location = await CRUD.create_location(db, location_data)
        assert location is not None

        initial_forecast_data = {
            "date": "2024-01-20",
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
            "raw_data": {"initial": "data"}
        }
        
        initial_forecasts = await CRUD.create_forecasts(
            db, location.id, [initial_forecast_data]
        )
        assert len(initial_forecasts) == 1
        updated_forecast_data = {
            "date": "2024-01-20",
            "temperature_min": -10.0,
            "temperature_max": 0.0,
            "temperature_avg": -5.0,
            "precipitation_probability": 0.5,
            "precipitation_amount": 2.0,
            "weather_code": 1003,
            "weather_description": "Partly cloudy",
            "wind_speed": 15.0,
            "humidity": 80,
            "sunrise": "08:30 AM",
            "sunset": "04:30 PM",
            "raw_data": {"updated": "data"}
        }
        updated_forecasts = await CRUD.create_forecasts(
            db, location.id, [updated_forecast_data]
        )
        assert len(updated_forecasts) == 1
        assert updated_forecasts[0].temperature_min == -10.0
        assert updated_forecasts[0].temperature_avg == -5.0
        assert updated_forecasts[0].is_cached == True
        
        query = select(WeatherForecast).where(
            WeatherForecast.location_id == location.id,
            WeatherForecast.date == date(2024, 1, 20)
        )
        result = await db.execute(query)
        db_forecast = result.scalar_one_or_none()
        assert db_forecast is not None
        assert db_forecast.temperature_min == -10.0