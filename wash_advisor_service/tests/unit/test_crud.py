import pytest
from datetime import date, timedelta
from app.schemas import UserContextData
from app.crud import CRUD


class TestCRUDOperations:
    """Тесты для CRUD операций"""
    
    @pytest.mark.asyncio
    async def test_get_user_context_not_found(self, db):
        """Получение несуществующего контекста пользователя"""
        context = await CRUD.get_user_context(db, "nonexistent_user")
        assert context is None
    
    @pytest.mark.asyncio
    async def test_create_user_context_success(self, db, sample_user_context_data):
        """Успешное создание контекста пользователя"""
        context = await CRUD.create_or_update_user_context(
            db,
            "new_user_123",
            sample_user_context_data
        )
        assert context is not None
        assert context.user_id == "new_user_123"
        assert context.city == sample_user_context_data.city
        assert context.country == sample_user_context_data.country
        assert context.last_wash_date == sample_user_context_data.last_wash_date
    
    @pytest.mark.asyncio
    async def test_update_user_context_success(self, db, sample_user_context_data):
        """Успешное обновление контекста пользователя"""
        context1 = await CRUD.create_or_update_user_context(
            db,
            "update_user_123",
            sample_user_context_data
        )
        assert context1 is not None
        updated_data = UserContextData(
            city="Saint Petersburg",
            country="Russia",
            last_wash_date=date.today(),
            preferred_wash_interval=10
        )
        context2 = await CRUD.create_or_update_user_context(
            db,
            "update_user_123",
            updated_data
        )
        assert context2 is not None
        assert context2.user_id == "update_user_123"
        assert context2.city == "Saint Petersburg"
        assert context2.last_wash_date == date.today()
        assert context2.preferred_wash_interval == 10
    
    @pytest.mark.asyncio
    async def test_calculate_user_context_with_last_wash(self, test_user_context):
        """Расчет контекста пользователя с датой последней мойки"""
        context_metrics = await CRUD.calculate_user_context(test_user_context)
        assert context_metrics["days_since_last_wash"] == 10
        assert context_metrics["is_interval_optimal"] == True
    
    @pytest.mark.asyncio
    async def test_calculate_user_context_without_last_wash(self, db, sample_user_context_data):
        """Расчет контекста пользователя без даты последней мойки"""
        no_wash_data = UserContextData(
            city="Moscow",
            country="Russia",
            last_wash_date=None,
            preferred_wash_interval=7
        )
        
        context = await CRUD.create_or_update_user_context(db, "no_wash_user", no_wash_data)
        context_metrics = await CRUD.calculate_user_context(context)
        assert context_metrics["days_since_last_wash"] is None
        assert context_metrics["is_interval_optimal"] is None
    
    @pytest.mark.asyncio
    async def test_get_cached_recommendation_not_found(self, db):
        """Получение несуществующей кэшированной рекомендации"""
        recommendation = await CRUD.get_cached_recommendation(
            db,
            "test_user",
            "Moscow",
            days=7
        )
        assert recommendation is None
    
    @pytest.mark.asyncio
    async def test_create_and_get_cached_recommendation(self, db):
        """Создание и получение кэшированной рекомендации"""
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

        user_context = {
            "days_since_last_wash": 10,
            "is_interval_optimal": True
        }
        recommendation = await CRUD.create_recommendation(
            db,
            "cache_user",
            "Moscow",
            date.today(),
            weather_data,
            analysis_results,
            user_context
        )
        await db.commit()
        assert recommendation is not None
        assert recommendation.user_id == "cache_user"
        assert recommendation.location == "Moscow"
        assert recommendation.is_recommended == True
        assert recommendation.score == 85.0
        
    @pytest.mark.asyncio
    async def test_get_user_recommendations(self, db):
        """Получение истории рекомендаций пользователя"""
        for i in range(3):
            weather_data = {
                "temperature": 15.0 + i,
                "precipitation_probability": 0.1,
                "precipitation_amount": 0.5,
                "wind_speed": 10.0,
                "humidity": 60,
                "weather_description": "Sunny",
                "raw_data": {"test": "data"}
            }

            analysis_results = {
                "is_recommended": True,
                "score": 80.0 + i,
                "reason": f"Условия {i}",
                "is_rain_expected": False,
                "is_temperature_optimal": True,
                "is_wind_acceptable": True
            }

            await CRUD.create_recommendation(
                db,
                "history_user",
                "Moscow",
                date.today() - timedelta(days=i),
                weather_data,
                analysis_results,
                {"days_since_last_wash": 10, "is_interval_optimal": True}
            )
        await db.commit()
        recommendations = await CRUD.get_user_recommendations(db, "history_user", limit=10)
        assert len(recommendations) == 3
        assert all(r.user_id == "history_user" for r in recommendations)
