from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc
from datetime import datetime, date, timedelta
import logging
from typing import Optional, List, Dict, Any

from app.models import WashRecommendation, UserContext
from app.schemas import UserContextData
from app.config import settings

logger = logging.getLogger(__name__)

class CRUD:
    """CRUD операции для работы с базой данных"""

    @staticmethod
    async def get_user_context(
        session: AsyncSession,
        user_id: str
    ) -> Optional[UserContext]:
        """Получить контекст пользователя"""
        try:
            query = select(UserContext).where(
                UserContext.user_id == user_id
            )
            
            result = await session.execute(query)
            context = result.scalar_one_or_none()
            if context:
                logger.debug(f"Found user context for {user_id}")
            else:
                logger.debug(f"No user context found for {user_id}")
            return context
            
        except Exception as e:
            logger.error(f"Error getting user context for {user_id}: {str(e)}")
            return None
    
    @staticmethod
    async def create_or_update_user_context(
        session: AsyncSession,
        user_id: str,
        context_data: UserContextData
    ) -> Optional[UserContext]:
        """Создать или обновить контекст пользователя"""
        try:
            existing = await CRUD.get_user_context(session, user_id)
            
            if existing:
                existing.city = context_data.city
                existing.country = context_data.country
                existing.last_wash_date = context_data.last_wash_date
                existing.preferred_wash_interval = context_data.preferred_wash_interval
                existing.last_sync = datetime.now()
                
                await session.flush()
                await session.refresh(existing)
                
                logger.debug(f"Updated user context for {user_id}")
                return existing
            else:
                context = UserContext(
                    user_id=user_id,
                    city=context_data.city,
                    country=context_data.country,
                    last_wash_date=context_data.last_wash_date,
                    preferred_wash_interval=context_data.preferred_wash_interval,
                    last_sync=datetime.now()
                )
                
                session.add(context)
                await session.flush()
                await session.refresh(context)
                
                logger.info(f"Created user context for {user_id}")
                return context
                
        except Exception as e:
            logger.error(f"Error creating/updating user context {user_id}: {str(e)}")
            await session.rollback()
            return None
    
    @staticmethod
    async def calculate_user_context(
        context: UserContext
    ) -> Dict[str, Any]:
        """Рассчитать дополнительные метрики на основе контекста"""
        try:
            if not context.last_wash_date:
                logger.debug(f"No last wash date for user {context.user_id}")
                return {
                    "days_since_last_wash": None,
                    "is_interval_optimal": None
                }
            
            days_since = (datetime.now().date() - context.last_wash_date).days
            
            is_optimal = days_since >= context.preferred_wash_interval

            logger.debug(f"Calculated context for user {context.user_id}: days_since={days_since}, is_optimal={is_optimal}")
            
            return {
                "days_since_last_wash": days_since,
                "is_interval_optimal": is_optimal
            }
        except Exception as e:
            logger.error(f"Error calculating user context: {str(e)}")
            return {
                "days_since_last_wash": None,
                "is_interval_optimal": None
            }
        
    @staticmethod
    async def get_cached_recommendation(
        session: AsyncSession,
        user_id: str,
        location: str,
        days: int = 7
    ) -> Optional[WashRecommendation]:
        """Получить кэшированную рекомендацию"""
        try:
            cache_limit = datetime.now() - timedelta(hours=settings.CACHE_RECOMMENDATION_HOURS)
            
            query = (
                select(WashRecommendation)
                .where(
                    and_(
                        WashRecommendation.user_id == user_id,
                        WashRecommendation.location == location,
                        WashRecommendation.created_at >= cache_limit,
                        WashRecommendation.is_recommended == True
                    )
                )
                .order_by(desc(WashRecommendation.created_at))
                .limit(1)
            )
            
            result = await session.execute(query)
            recommendation = result.scalar_one_or_none()
            
            if recommendation:
                logger.info(f"Found cached recommendation for user {user_id} in {location}")
                return recommendation
            
            logger.debug(f"No cached recommendation for user {user_id} in {location}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cached recommendation {user_id}: {str(e)}")
            return None
    
    @staticmethod
    async def create_recommendation(
        session: AsyncSession,
        user_id: str,
        location: str,
        recommendation_date: date,
        weather_data: Dict[str, Any],
        analysis_results: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None
    ) -> Optional[WashRecommendation]:
        """Создать новую рекомендацию"""
        try:
            expires_at = datetime.now() + timedelta(hours=24)
            temperature = weather_data.get('temperature') or weather_data.get('temperature_avg')
            
            recommendation = WashRecommendation(
                user_id=user_id,
                location=location,
                recommendation_date=recommendation_date,
                temperature=temperature,
                precipitation_probability=weather_data.get('precipitation_probability'),
                precipitation_amount=weather_data.get('precipitation_amount'),
                wind_speed=weather_data.get('wind_speed'),
                humidity=weather_data.get('humidity'),
                weather_description=weather_data.get('weather_description'),
                score=analysis_results.get('score'),
                is_recommended=analysis_results['is_recommended'],
                reason=analysis_results.get('reason'),
                is_rain_expected=analysis_results.get('is_rain_expected', False),
                is_temperature_optimal=analysis_results.get('is_temperature_optimal', False),
                is_wind_acceptable=analysis_results.get('is_wind_acceptable', False),
                days_since_last_wash=user_context.get('days_since_last_wash') if user_context else None,
                is_interval_optimal=user_context.get('is_interval_optimal') if user_context else None,
                raw_forecast_data=weather_data.get('raw_data'),
                expires_at=expires_at
            )
            
            session.add(recommendation)
            await session.flush()
            await session.refresh(recommendation)
            
            logger.info(f"Created new recommendation for user {user_id}: {recommendation_date}")
            return recommendation
            
        except Exception as e:
            logger.error(f"Error creating recommendation for user {user_id}: {str(e)}")
            await session.rollback()
            return None
    
    @staticmethod
    async def get_user_recommendations(
        session: AsyncSession,
        user_id: str,
        limit: int = 10
    ) -> List[WashRecommendation]:
        """Получить историю рекомендаций пользователя"""
        try:
            query = (
                select(WashRecommendation)
                .where(WashRecommendation.user_id == user_id)
                .order_by(desc(WashRecommendation.created_at))
                .limit(limit)
            )
            
            result = await session.execute(query)
            recommendations = result.scalars().all()

            logger.info(f"Retrieved {len(recommendations)} recommendations for user {user_id}")
            return recommendations
            
        except Exception as e:
            logger.error(f"Error getting user recommendations for {user_id}: {str(e)}")
            return []
    
    @staticmethod
    async def get_service_stats(
        session: AsyncSession,
        days: int = 30
    ) -> Dict[str, Any]:
        """Получить общую статистику сервиса"""
        try:
            time_limit = datetime.now() - timedelta(days=days)
            total_rec_query = select(func.count(WashRecommendation.id)).where(
                WashRecommendation.created_at >= time_limit
            )
            total_rec_result = await session.execute(total_rec_query)
            total_recommendations = total_rec_result.scalar() or 0
            successful_rec_query = select(func.count(WashRecommendation.id)).where(
                and_(
                    WashRecommendation.created_at >= time_limit,
                    WashRecommendation.is_recommended == True
                )
            )
            successful_rec_result = await session.execute(successful_rec_query)
            successful_recommendations = successful_rec_result.scalar() or 0
            avg_score_query = select(func.avg(WashRecommendation.score)).where(
                WashRecommendation.created_at >= time_limit
            )
            avg_score_result = await session.execute(avg_score_query)
            avg_score = avg_score_result.scalar()
            unique_users_query = select(func.count(func.distinct(WashRecommendation.user_id))).where(
                WashRecommendation.created_at >= time_limit
            )
            unique_users_result = await session.execute(unique_users_query)
            unique_users = unique_users_result.scalar() or 0
            
            stats = {
                "total_recommendations": total_recommendations,
                "successful_recommendations": successful_recommendations,
                "average_recommendation_score": round(avg_score, 2) if avg_score else None,
                "total_users": unique_users,
                "timestamp": datetime.now()
            }
            
            logger.info(f"Service stats for last {days} days: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting service stats: {str(e)}")
            return {}