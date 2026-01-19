import pytest
from unittest.mock import patch
from datetime import date
import uuid

from app.crud import CRUD, hash_password, verify_password
from app.models import User
from app.schemas import UserCreate, UserUpdate

class TestPasswordUtils:
    """Тесты для утилит работы с паролями"""
    
    def test_hash_password_success(self):
        """Успешное хеширование пароля"""
        plain_password = "mysecretpassword123"
        hashed = hash_password(plain_password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != plain_password
    
    @patch("app.crud.bcrypt.gensalt")
    def test_hash_password_error(self, mock_gensalt):
        """Ошибка при хешировании пароля"""
        mock_gensalt.side_effect = Exception("BCrypt error")
        with pytest.raises(Exception):
            hash_password("testpassword")
    
    def test_verify_password_correct(self):
        """Проверка верного пароля"""
        plain_password = "test123"
        hashed = hash_password(plain_password)
        result = verify_password(plain_password, hashed)
        assert result is True
    
    def test_verify_password_incorrect(self):
        """Проверка неверного пароля"""
        plain_password = "test123"
        wrong_password = "wrong123"
        hashed = hash_password(plain_password)
        result = verify_password(wrong_password, hashed)
        assert result is False
    
    @patch("app.crud.bcrypt.checkpw")
    def test_verify_password_error(self, mock_checkpw):
        """Ошибка при проверке пароля"""
        mock_checkpw.side_effect = Exception("Verification error")
        result = verify_password("test", "hashed")
        assert result is False


class TestCRUDOperations:
    """Тесты для CRUD операций"""
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, clean_db, test_user):
        """Успешное получение пользователя по ID"""
        result = await CRUD.get_user_by_id(clean_db, test_user.id)
        assert result is not None
        assert result.id == test_user.id
        assert result.username == test_user.username
        assert result.email == test_user.email
    
    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, clean_db):
        """Пользователь не найден по ID"""
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        result = await CRUD.get_user_by_id(clean_db, non_existent_id)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_by_username_success(self, clean_db, test_user):
        """Успешное получение пользователя по имени"""
        result = await CRUD.get_user_by_username(clean_db, test_user.username)
        assert result is not None
        assert result.username == test_user.username
        assert result.id == test_user.id
    
    @pytest.mark.asyncio
    async def test_get_user_by_username_not_found(self, clean_db):
        """Пользователь не найден по имени"""
        result = await CRUD.get_user_by_username(clean_db, "nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_user_by_email_success(self, clean_db, test_user):
        """Успешное получение пользователя по email"""
        result = await CRUD.get_user_by_email(clean_db, test_user.email)
        assert result is not None
        assert result.email == test_user.email
    
    @pytest.mark.asyncio
    async def test_get_all_users(self, clean_db, test_user):
        """Получение всех пользователей"""
        from app.crud import hash_password
        another_user = User(
            username=f"anotheruser_{uuid.uuid4().hex[:8]}",
            email=f"another_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=hash_password("password123"),
            city="London",
            country="UK"
        )
        clean_db.add(another_user)
        await clean_db.commit()
        await clean_db.refresh(another_user)
        users = await CRUD.get_all_users(clean_db)
        assert len(users) >= 2
        user_ids = [user.id for user in users]
        assert test_user.id in user_ids
        assert another_user.id in user_ids
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, clean_db):
        """Успешное создание пользователя"""
        unique_id = uuid.uuid4().hex[:8]
        user_data = UserCreate(
            username=f"newuser_{unique_id}",
            email=f"new_{unique_id}@example.com",
            password="newpass123",
            city="Paris",
            country="France",
            preferred_wash_interval=10
        )
        user = await CRUD.create_user(clean_db, user_data)
        assert user is not None
        assert user.username == user_data.username
        assert user.email == user_data.email
        assert user.city == user_data.city
        assert user.preferred_wash_interval == user_data.preferred_wash_interval
        assert user.hashed_password != user_data.password
        assert user.id is not None
        assert verify_password(user_data.password, user.hashed_password)
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, clean_db, test_user):
        """Ошибка при создании пользователя с существующим именем"""
        duplicate_data = UserCreate(
            username=test_user.username,
            email="different@example.com",
            password="password123",
            city="City",
            country="Country"
        )
        result = await CRUD.create_user(clean_db, duplicate_data)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, clean_db, test_user):
        """Ошибка при создании пользователя с существующим email"""
        from app.schemas import UserCreate
        duplicate_data = UserCreate(
            username="differentuser",
            email=test_user.email,
            password="password123",
            city="City",
            country="Country"
        )
        result = await CRUD.create_user(clean_db, duplicate_data)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_user_success(self, clean_db, test_user):
        """Успешное обновление пользователя"""
        update_data = UserUpdate(
            city="Updated City",
            country="Updated Country",
            preferred_wash_interval=5
        )
        updated_user = await CRUD.update_user(
            clean_db, test_user.id, update_data
        )
        assert updated_user is not None
        assert updated_user.id == test_user.id
        assert updated_user.city == "Updated City"
        assert updated_user.country == "Updated Country"
        assert updated_user.preferred_wash_interval == 5
        assert updated_user.username == test_user.username
    
    @pytest.mark.asyncio
    async def test_update_user_not_found(self, clean_db):
        """Обновление несуществующего пользователя"""
        update_data = UserUpdate(city="New City")
        non_existent_id = "00000000-0000-0000-0000-000000000000"
        result = await CRUD.update_user(clean_db, non_existent_id, update_data)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_update_last_wash_date_success(self, clean_db, test_user):
        """Успешное обновление даты последней мойки"""
        wash_date = date(2024, 1, 15)
        result = await CRUD.update_last_wash_date(
            clean_db, test_user.id, wash_date
        )
        assert result is True
        await clean_db.refresh(test_user)
        assert test_user.last_wash_date == wash_date
    
    @pytest.mark.asyncio
    async def test_update_last_wash_date_user_not_found(self, clean_db):
        """Обновление даты мойки для несуществующего пользователя"""
        result = await CRUD.update_last_wash_date(
            clean_db, "non-existent-id", date.today()
        )
        assert result is False
    
    @pytest.mark.asyncio
    async def test_authenticate_user_success(self, clean_db):
        """Успешная аутентификация пользователя"""
        unique_id = uuid.uuid4().hex[:8]
        user_data = UserCreate(
            username=f"authuser_{unique_id}",
            email=f"auth_{unique_id}@example.com",
            password="authpass123",
            city="Berlin",
            country="Germany",
            preferred_wash_interval=7
        )
        
        user = await CRUD.create_user(clean_db, user_data)
        assert user is not None
        authenticated = await CRUD.authenticate_user(
            clean_db,
            user_data.username,
            user_data.password
        )
        assert authenticated is not None
        assert authenticated.id == user.id
        assert authenticated.username == user_data.username
    
    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, clean_db, test_user):
        """Аутентификация с неверным паролем"""
        result = await CRUD.authenticate_user(
            clean_db,
            test_user.username,
            "wrongpassword"
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, clean_db):
        """Аутентификация несуществующего пользователя"""
        result = await CRUD.authenticate_user(
            clean_db,
            "nonexistent",
            "password"
        )
        assert result is None
    
    @patch("app.crud.logger")
    @pytest.mark.asyncio
    async def test_crud_error_handling(self, mock_logger, mock_db_session):
        """Тестирование обработки ошибок в CRUD"""
        mock_db_session.execute.side_effect = Exception("Database error")
        result = await CRUD.get_user_by_id(mock_db_session, "123")
        assert result is None
        mock_logger.error.assert_called_once()