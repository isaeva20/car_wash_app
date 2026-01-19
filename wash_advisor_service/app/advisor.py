import logging
from typing import Dict, Any, List, Optional
from math import exp

from app.config import settings
from app.schemas import WashRecommendationDay

logger = logging.getLogger(__name__)

class WashAdvisorLogic:
    """Бизнес-логика для рекомендаций по мойке автомобиля"""
    
    @staticmethod
    def analyze_weather_day(
        weather_data: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Анализ погодных условий для конкретного дня"""
        logger.info(f"Analyzing weather day: {weather_data.get('date')}")
       
        temp = weather_data.get('temperature_avg')
        precip_prob = weather_data.get('precipitation_probability')
        precip_amount = weather_data.get('precipitation_amount')
        wind_speed = weather_data.get('wind_speed')
        humidity = weather_data.get('humidity')
        weather_desc = weather_data.get('weather_description', '')
        
        logger.info(f"Extracted data - temp: {temp}, precip: {precip_prob}, wind: {wind_speed}, humidity: {humidity}")
       
        is_rain_expected = precip_prob is not None and precip_prob > settings.MIN_PRECIPITATION_THRESHOLD
        is_temperature_optimal = temp is not None and settings.IDEAL_WASH_TEMPERATURE_MIN <= temp <= settings.IDEAL_WASH_TEMPERATURE_MAX
        is_wind_acceptable = wind_speed is not None and wind_speed <= settings.WIND_SPEED_THRESHOLD

        logger.info(f"Factor analysis - rain_expected: {is_rain_expected}, temp_optimal: {is_temperature_optimal}, wind_acceptable: {is_wind_acceptable}")
        
        score = WashAdvisorLogic._calculate_score(
            temp=temp,
            precip_prob=precip_prob,
            wind_speed=wind_speed,
            humidity=humidity,
            is_rain_expected=is_rain_expected,
            is_temperature_optimal=is_temperature_optimal,
            is_wind_acceptable=is_wind_acceptable
        )
        logger.info(f"Base score calculated: {score:.1f}")

        if user_context:
            days_since = user_context.get('days_since_last_wash')
            is_interval_optimal = user_context.get('is_interval_optimal')
            logger.info(f"User context - days_since: {days_since}, interval_optimal: {is_interval_optimal}")
            if days_since is not None and is_interval_optimal:
                old_score = score
                score = min(100, score + 10)
                logger.info(f"Added bonus for optimal interval: {old_score:.1f} → {score:.1f}")
            elif days_since is not None and days_since < 7:
                old_score = score
                score = max(0, score - 20)
                logger.info(f"Penalty for recent wash: {old_score:.1f} → {score:.1f}")
        
        reason = WashAdvisorLogic._generate_reason(
            is_rain_expected=is_rain_expected,
            is_temperature_optimal=is_temperature_optimal,
            is_wind_acceptable=is_wind_acceptable,
            precip_prob=precip_prob,
            temp=temp,
            wind_speed=wind_speed,
            score=score,
            user_context=user_context
        )

        logger.info(f"Final score: {score:.1f}, reason: {reason}")
        return {
            'date': weather_data['date'],
            'temperature': temp,
            'precipitation_probability': precip_prob,
            'precipitation_amount': precip_amount,
            'wind_speed': wind_speed,
            'humidity': humidity,
            'weather_description': weather_desc,
            'is_rain_expected': is_rain_expected,
            'is_temperature_optimal': is_temperature_optimal,
            'is_wind_acceptable': is_wind_acceptable,
            'score': score,
            'reason': reason
        }
    
    @staticmethod
    def _calculate_score(
        temp: Optional[float],
        precip_prob: Optional[float],
        wind_speed: Optional[float],
        humidity: Optional[int],
        is_rain_expected: bool,
        is_temperature_optimal: bool,
        is_wind_acceptable: bool
    ) -> float:
        """Расчет общего балла для дня"""
        logger.info("Starting score calculation")
        precip_score = 100.0
        if precip_prob is not None:
            precip_score = 100 * exp(-5 * precip_prob)
            logger.info(f"Precipitation score: {precip_score:.1f} (prob: {precip_prob})")
        
        temp_score = 50.0
        if temp is not None:
            if 15 <= temp <= 22:
                temp_score = 100.0
            elif 10 <= temp < 15 or 22 < temp <= 25:
                temp_score = 80.0
            elif 5 <= temp < 10 or 25 < temp <= 30:
                temp_score = 60.0
            else:
                if temp < 5:
                    temp_score = max(0, 60 - (5 - temp) * 10)
                else:
                    temp_score = max(0, 60 - (temp - 30) * 10)
            logger.info(f"Temperature score: {temp_score:.1f} (temp: {temp}°C)")
        
        wind_score = 100.0
        if wind_speed is not None:
            if wind_speed <= 15:
                wind_score = 100.0
            elif wind_speed <= 25:
                wind_score = 80.0
            elif wind_speed <= 35:
                wind_score = 50.0
            else:
                wind_score = 20.0
            logger.info(f"Wind score: {wind_score:.1f} (speed: {wind_speed} km/h)")
        
        humidity_score = 80.0
        if humidity is not None:
            if 40 <= humidity <= 60:
                humidity_score = 100.0
            elif 30 <= humidity < 40 or 60 < humidity <= 70:
                humidity_score = 80.0
            elif 20 <= humidity < 30 or 70 < humidity <= 80:
                humidity_score = 60.0
            else:
                humidity_score = 40.0
            logger.info(f"Humidity score: {humidity_score:.1f} (humidity: {humidity}%)")
        
        penalty = 0
        if is_rain_expected:
            penalty += 40
            logger.info(f"Penalty for expected rain: +40")
        if not is_temperature_optimal:
            penalty += 20
            logger.info(f"Penalty for non-optimal temperature: +20")
        if not is_wind_acceptable:
            penalty += 20
            logger.info(f"Penalty for unacceptable wind: +20")
        
        total_score = (
            precip_score * settings.WEIGHT_PRECIPITATION +
            temp_score * settings.WEIGHT_TEMPERATURE +
            wind_score * settings.WEIGHT_WIND +
            humidity_score * settings.WEIGHT_HUMIDITY
        ) - penalty
        
        final_score = max(0, min(100, total_score))
        
        if final_score != total_score:
            logger.info(f"Score bounded: {total_score:.1f} → {final_score:.1f}")
        
        return final_score
    
    @staticmethod
    def _generate_reason(
        is_rain_expected: bool,
        is_temperature_optimal: bool,
        is_wind_acceptable: bool,
        precip_prob: Optional[float],
        temp: Optional[float],
        wind_speed: Optional[float],
        score: float,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Генерация текстового объяснения рекомендации"""

        logger.info("Generating recommendation reason")
        
        reasons = []
        
        if is_rain_expected and precip_prob is not None:
            reasons.append(f"Высокая вероятность дождя ({precip_prob*100:.0f}%)")
            logger.info(f"Added rain reason: {precip_prob*100:.0f}%")
        
        if not is_temperature_optimal:
            if temp is not None:
                if temp < 5:
                    reasons.append(f"Низкая температура ({temp:.0f}°C)")
                    logger.info(f"Added low temp reason: {temp:.0f}°C")
                elif temp > 25:
                    reasons.append(f"Высокая температура ({temp:.0f}°C)")
                    logger.info(f"Added high temp reason: {temp:.0f}°C")
        
        if not is_wind_acceptable and wind_speed is not None:
            reasons.append(f"Сильный ветер ({wind_speed:.0f} км/ч)")
            logger.info(f"Added wind reason: {wind_speed:.0f} км/ч")
        if user_context:
            days_since = user_context.get('days_since_last_wash')
            is_interval_optimal = user_context.get('is_interval_optimal')
            
            if days_since is not None:
                if is_interval_optimal:
                    reasons.append(f"Оптимальный интервал ({days_since} дней с последней мойки)")
                    logger.debug(f"Added optimal interval reason: {days_since} дней")
                elif days_since < 7:
                    reasons.append(f"Недавняя мойка ({days_since} дней назад)")
                    logger.debug(f"Added recent wash reason: {days_since} дней")

        
        if score >= 80:
            if not reasons:
                result = "Отличные условия для мойки"
            else:
                result = f"Хорошие условия, но {', '.join(reasons).lower()}"
                logger.info("Good conditions with issues")
        elif score >= 60:
            if reasons:
                result = f"Удовлетворительные условия, однако {', '.join(reasons).lower()}"
                logger.info("Satisfactory conditions with issues")
            else:
                result = "Удовлетворительные условия для мойки"
                logger.info("Satisfactory conditions")
        elif score >= 40:
            result = f"Неблагоприятные условия: {', '.join(reasons)}" if reasons else "Неблагоприятные условия"
            logger.info("Unfavorable conditions")
        else:
            result = f"Очень плохие условия: {', '.join(reasons)}" if reasons else "Очень плохие условия"
            logger.info("Very bad conditions without specific reasons")

        logger.info(f"Final reason: {result}")
        return result
    
    @staticmethod
    def find_best_wash_day(
        analyzed_days: List[Dict[str, Any]],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[WashRecommendationDay]:
        """Найти лучший день для мойки"""

        logger.info(f"Finding best wash day from {len(analyzed_days)} analyzed days")
        
        if not analyzed_days:
            logger.warning("No analyzed days provided")
            return None
        
        min_acceptable_score = 60.0
        
        acceptable_days = [
            day for day in analyzed_days 
            if day['score'] and day['score'] >= min_acceptable_score
        ]
        
        if not acceptable_days:
            logger.warning(f"No days meet minimum score, using all {len(acceptable_days)} days")
            acceptable_days = analyzed_days
        
        sorted_days = sorted(
            acceptable_days, 
            key=lambda x: x['score'] if x['score'] else 0, 
            reverse=True
        )
        
        best_day = sorted_days[0]
        
        return WashRecommendationDay(
            date=best_day['date'],
            is_recommended=best_day['score'] >= min_acceptable_score if best_day['score'] else False,
            score=best_day['score'] or 0,
            temperature=best_day['temperature'],
            precipitation_probability=best_day['precipitation_probability'],
            wind_speed=best_day['wind_speed'],
            reason=best_day['reason'] or "",
            factors={
                "is_rain_expected": best_day['is_rain_expected'],
                "is_temperature_optimal": best_day['is_temperature_optimal'],
                "is_wind_acceptable": best_day['is_wind_acceptable'],
                "humidity": best_day['humidity']
            }
        )
    
    @staticmethod
    def generate_all_days_recommendations(
        analyzed_days: List[Dict[str, Any]]
    ) -> List[WashRecommendationDay]:
        """Сгенерировать рекомендации для всех дней"""
        
        min_acceptable_score = 60.0
        recommendations = []
        
        for day in analyzed_days:
            is_recommended = day['score'] is not None and day['score'] >= min_acceptable_score
            
            rec_day = WashRecommendationDay(
                date=day['date'],
                is_recommended=is_recommended,
                score=day['score'] or 0,
                temperature=day['temperature'],
                precipitation_probability=day['precipitation_probability'],
                wind_speed=day['wind_speed'],
                reason=day['reason'] or "",
                factors={
                    "is_rain_expected": day['is_rain_expected'],
                    "is_temperature_optimal": day['is_temperature_optimal'],
                    "is_wind_acceptable": day['is_wind_acceptable'],
                    "humidity": day['humidity']
                }
            )
            
            recommendations.append(rec_day)
        
        return recommendations
    