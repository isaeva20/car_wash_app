import pytest
from datetime import date, timedelta
from unittest.mock import patch

class TestWashAdvisorLogic:
    """Тесты для бизнес-логики рекомендаций по мойке"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Настройка перед каждым тестом"""
        from app.advisor import WashAdvisorLogic
        from app.config import settings
        self.WashAdvisorLogic = WashAdvisorLogic
        self.settings = settings
    
    def test_analyze_weather_day_ideal_conditions(self, mock_advisor_logger):
        """Анализ идеальных погодных условий"""
        weather_data = {
            "date": date.today().isoformat(),
            "temperature_avg": 20.0,
            "precipitation_probability": 0.1,
            "precipitation_amount": 0.5,
            "wind_speed": 10.0,
            "humidity": 50,
            "weather_description": "Sunny"
        }
        result = self.WashAdvisorLogic.analyze_weather_day(weather_data)
        assert result["date"] == weather_data["date"]
        assert result["temperature"] == 20.0
        assert result["precipitation_probability"] == 0.1
        assert result["is_rain_expected"] == False
        assert result["is_temperature_optimal"] == True
        assert result["is_wind_acceptable"] == True
        assert result["score"] >= 80
        assert "Отличные условия для мойки" in result["reason"]
    
    def test_analyze_weather_day_rain_expected(self, mock_advisor_logger):
        """Анализ с ожиданием дождя"""
        weather_data = {
            "date": date.today().isoformat(),
            "temperature_avg": 18.0,
            "precipitation_probability": 0.8,
            "precipitation_amount": 5.0,
            "wind_speed": 5.0,
            "humidity": 70,
            "weather_description": "Rainy"
        }
        result = self.WashAdvisorLogic.analyze_weather_day(weather_data)
        assert result["is_rain_expected"] == True
        assert result["score"] < 70
        assert "Высокая вероятность дождя" in result["reason"]
    
    def test_analyze_weather_day_cold_temperature(self, mock_advisor_logger):
        """Анализ с низкой температурой"""
        weather_data = {
            "date": date.today().isoformat(),
            "temperature_avg": -5.0,
            "precipitation_probability": 0.0,
            "precipitation_amount": 0.0,
            "wind_speed": 5.0,
            "humidity": 40,
            "weather_description": "Clear"
        }
        result = self.WashAdvisorLogic.analyze_weather_day(weather_data)
        assert result["is_temperature_optimal"] == False
        assert result["score"] < 60
        assert "Низкая температура" in result["reason"]
    
    def test_analyze_weather_day_high_wind(self, mock_advisor_logger):
        """Анализ с сильным ветром"""
        weather_data = {
            "date": date.today().isoformat(),
            "temperature_avg": 15.0,
            "precipitation_probability": 0.1,
            "precipitation_amount": 0.0,
            "wind_speed": 40.0,
            "humidity": 50,
            "weather_description": "Windy"
        }
        result = self.WashAdvisorLogic.analyze_weather_day(weather_data)
        assert result["is_wind_acceptable"] == False
        assert result["score"] < 70
        assert "Сильный ветер" in result["reason"]
    
    def test_analyze_weather_day_with_user_context_optimal(self, mock_advisor_logger):
        """Анализ с оптимальным пользовательским контекстом"""
        weather_data = {
            "date": date.today().isoformat(),
            "temperature_avg": 18.0,
            "precipitation_probability": 0.2,
            "precipitation_amount": 1.0,
            "wind_speed": 10.0,
            "humidity": 55,
            "weather_description": "Partly cloudy"
        }

        user_context = {
            "days_since_last_wash": 10,
            "is_interval_optimal": True
        }
        result_with_context = self.WashAdvisorLogic.analyze_weather_day(weather_data, user_context)
        result_without_context = self.WashAdvisorLogic.analyze_weather_day(weather_data)
        assert result_with_context["score"] >= result_without_context["score"]
        assert "оптимальный" in result_with_context["reason"].lower()

    
    def test_analyze_weather_day_with_user_context_recent_wash(self, mock_advisor_logger):
        """Анализ с недавней мойкой"""
        weather_data = {
            "date": date.today().isoformat(),
            "temperature_avg": 20.0,
            "precipitation_probability": 0.1,
            "precipitation_amount": 0.0,
            "wind_speed": 5.0,
            "humidity": 50,
            "weather_description": "Sunny"
        }

        user_context = {
            "days_since_last_wash": 2,
            "is_interval_optimal": False
        }
        result = self.WashAdvisorLogic.analyze_weather_day(weather_data, user_context)
        assert result["score"] < 80
        assert "недавн" in result["reason"].lower()
    
    def test_calculate_score_ideal_conditions(self, mock_advisor_logger):
        """Расчет балла для идеальных условий"""
        score = self.WashAdvisorLogic._calculate_score(
            temp=20.0,
            precip_prob=0.1,
            wind_speed=10.0,
            humidity=50,
            is_rain_expected=False,
            is_temperature_optimal=True,
            is_wind_acceptable=True
        )
        assert 80 <= score <= 100
    
    def test_calculate_score_bad_conditions(self, mock_advisor_logger):
        """Расчет балла для плохих условий"""
        score = self.WashAdvisorLogic._calculate_score(
            temp=35.0,
            precip_prob=0.9,
            wind_speed=40.0,
            humidity=90,
            is_rain_expected=True,
            is_temperature_optimal=False,
            is_wind_acceptable=False
        )
        assert score < 40
    
    def test_generate_reason_high_score(self, mock_advisor_logger):
        """Генерация причины для высокого балла"""
        reason = self.WashAdvisorLogic._generate_reason(
            is_rain_expected=False,
            is_temperature_optimal=True,
            is_wind_acceptable=True,
            precip_prob=0.1,
            temp=20.0,
            wind_speed=10.0,
            score=90.0
        )
        assert "Отличные условия для мойки" in reason
    
    def test_generate_reason_medium_score_with_issues(self, mock_advisor_logger):
        """Генерация причины для среднего балла с проблемами"""
        reason = self.WashAdvisorLogic._generate_reason(
            is_rain_expected=True,
            is_temperature_optimal=False,
            is_wind_acceptable=True,
            precip_prob=0.4,
            temp=30.0,
            wind_speed=15.0,
            score=65.0
        )
        assert "дожд" in reason.lower() or "осадк" in reason.lower()
    
    def test_find_best_wash_day(self, mock_advisor_logger):
        """Поиск лучшего дня для мойки"""
        analyzed_days = [
            {
                "date": date.today().isoformat(),
                "score": 85.0,
                "temperature": 20.0,
                "precipitation_probability": 0.1,
                "wind_speed": 10.0,
                "reason": "Отличные условия",
                "is_rain_expected": False,
                "is_temperature_optimal": True,
                "is_wind_acceptable": True,
                "humidity": 50
            },
            {
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "score": 45.0,
                "temperature": 8.0,
                "precipitation_probability": 0.8,
                "wind_speed": 20.0,
                "reason": "Плохие условия",
                "is_rain_expected": True,
                "is_temperature_optimal": False,
                "is_wind_acceptable": True,
                "humidity": 85
            }
        ]
        best_day = self.WashAdvisorLogic.find_best_wash_day(analyzed_days)
        assert best_day is not None
        assert best_day.date == date.today()
        assert best_day.score == 85.0
        assert best_day.is_recommended == True
        assert "Отличные условия" in best_day.reason
    
    def test_find_best_wash_day_no_acceptable_days(self, mock_advisor_logger):
        """Поиск лучшего дня, когда нет приемлемых дней"""
        analyzed_days = [
            {
                "date": date.today().isoformat(),
                "score": 45.0,
                "temperature": 8.0,
                "precipitation_probability": 0.8,
                "wind_speed": 20.0,
                "reason": "Плохие условия",
                "is_rain_expected": True,
                "is_temperature_optimal": False,
                "is_wind_acceptable": True,
                "humidity": 85
            },
            {
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "score": 30.0,
                "temperature": 5.0,
                "precipitation_probability": 0.9,
                "wind_speed": 25.0,
                "reason": "Очень плохие условия",
                "is_rain_expected": True,
                "is_temperature_optimal": False,
                "is_wind_acceptable": False,
                "humidity": 90
            }
        ]
        best_day = self.WashAdvisorLogic.find_best_wash_day(analyzed_days)
        assert best_day is not None
        assert best_day.score == 45.0
        assert best_day.is_recommended == False
    
    def test_generate_all_days_recommendations(self, mock_advisor_logger):
        """Генерация рекомендаций для всех дней"""
        analyzed_days = [
            {
                "date": date.today().isoformat(),
                "score": 85.0,
                "temperature": 20.0,
                "precipitation_probability": 0.1,
                "wind_speed": 10.0,
                "reason": "Отличные условия",
                "is_rain_expected": False,
                "is_temperature_optimal": True,
                "is_wind_acceptable": True,
                "humidity": 50
            },
            {
                "date": (date.today() + timedelta(days=1)).isoformat(),
                "score": 45.0,
                "temperature": 8.0,
                "precipitation_probability": 0.8,
                "wind_speed": 20.0,
                "reason": "Плохие условия",
                "is_rain_expected": True,
                "is_temperature_optimal": False,
                "is_wind_acceptable": True,
                "humidity": 85
            }
        ]
        recommendations = self.WashAdvisorLogic.generate_all_days_recommendations(analyzed_days)
        assert len(recommendations) == 2
        assert recommendations[0].date == date.today()
        assert recommendations[0].score == 85.0
        assert recommendations[0].is_recommended == True
        assert recommendations[1].date == date.today() + timedelta(days=1)
        assert recommendations[1].score == 45.0
        assert recommendations[1].is_recommended == False