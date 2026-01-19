from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import Optional, List
from datetime import date
import bcrypt
import logging

from app.models import User
from app.schemas import UserCreate, UserUpdate


logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """Хеширование пароля с использованием bcrypt"""
    try:
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Error hashing password: {str(e)}")
        raise

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        ) 
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False

class CRUD:
    """CRUD операции для пользователей"""
    
    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
        """Получить пользователя по ID"""
        try:
            query = select(User).where(User.id == user_id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {str(e)}")
            return None
    
    @staticmethod
    async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
        """Получить пользователя по имени"""
        try:
            query = select(User).where(User.username == username)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by username {username}: {str(e)}")
            return None
    
    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
        """Получить пользователя по email"""
        try:
            query = select(User).where(User.email == email)
            result = await session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting user by email {email}: {str(e)}")
            return None
    
    @staticmethod
    async def get_all_users(session: AsyncSession) -> List[User]:
        """Получить всех пользователей из базы данных"""
        try:
            query = select(User).order_by(User.created_at.desc())
            result = await session.execute(query)
            users = result.scalars().all()
            logger.info(f"Retrieved {len(users)} users from database")
            return users
        except Exception as e:
            logger.error(f"Error getting all users: {str(e)}")
            return []
    
    @staticmethod
    async def create_user(session: AsyncSession, user_data: UserCreate) -> Optional[User]:
        """Создать нового пользователя"""
        try:
            # Проверяем существование пользователя
            existing_user = await CRUD.get_user_by_username(session, user_data.username)
            if existing_user:
                logger.warning(f"User {user_data.username} already exists")
                return None
            
            existing_email = await CRUD.get_user_by_email(session, user_data.email)
            if existing_email:
                logger.warning(f"Email {user_data.email} already exists")
                return None
            
            # Создаем пользователя
            user = User(
                username=user_data.username,
                email=user_data.email,
                hashed_password=hash_password(user_data.password),
                city=user_data.city,
                country=user_data.country,
                preferred_wash_interval=user_data.preferred_wash_interval
            )
            
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            logger.info(f"Created new user: {user.username} (ID: {user.id})")
            return user
            
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            await session.rollback()
            return None
    
    @staticmethod
    async def update_user(
        session: AsyncSession, 
        user_id: str, 
        user_data: UserUpdate
    ) -> Optional[User]:
        """Обновить пользователя"""
        try:
            user = await CRUD.get_user_by_id(session, user_id)
            if not user:
                return None
            
            update_data = user_data.dict(exclude_unset=True)
            if update_data:
                query = (
                    update(User)
                    .where(User.id == user_id)
                    .values(**update_data)
                )
                await session.execute(query)
                await session.commit()
                await session.refresh(user)
            
            logger.info(f"Updated user: {user.username}")
            return user
            
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            await session.rollback()
            return None
    
    @staticmethod
    async def update_last_wash_date(
        session: AsyncSession,
        user_id: str,
        wash_date: date
    ) -> bool:
        """Обновить дату последней мойки"""
        try:
            user = await CRUD.get_user_by_id(session, user_id)
            if not user:
                return False
            
            user.last_wash_date = wash_date
            await session.commit()
            
            logger.info(f"Updated last wash date for user {user.username}: {wash_date}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating wash date for user {user_id}: {str(e)}")
            await session.rollback()
            return False
    
    @staticmethod
    async def authenticate_user(
        session: AsyncSession, 
        username: str, 
        password: str
    ) -> Optional[User]:
        """Аутентификация пользователя"""
        try:
            user = await CRUD.get_user_by_username(session, username)
            if not user:
                return None
            
            if not verify_password(password, user.hashed_password):
                return None

            return user
            
        except Exception as e:
            logger.error(f"Error authenticating user {username}: {str(e)}")
            return None