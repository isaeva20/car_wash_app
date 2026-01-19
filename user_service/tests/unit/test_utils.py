import pytest
from datetime import datetime, date
from pydantic import ValidationError

from app.schemas import UserCreate, UserUpdate, UserLogin, UserResponse


class TestSchemas:
    """Тесты для Pydantic схем"""
    
    def test_user_create_valid(self):
        """Валидные данные для создания пользователя"""
        user = UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123",
            city="Moscow",
            country="Russia",
            preferred_wash_interval=7
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.password == "password123"
        assert user.city == "Moscow"
        assert user.preferred_wash_interval == 7
    
    def test_user_create_invalid_username(self):
        """Невалидное имя пользователя"""
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(
                username="",
                email="test@example.com",
                password="password123"
            )
        
        errors = exc_info.value.errors()
        assert any("Имя пользователя" in str(error.get('msg', '')) for error in errors)
    
    def test_user_create_short_password(self):
        """Слишком короткий пароль"""
        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="123"
            )
    
    def test_user_create_password_with_spaces(self):
        """Пароль с пробелами"""
        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="test@example.com",
                password="pass word"
            )
    
    def test_user_create_invalid_email(self):
        """Невалидный email"""
        with pytest.raises(ValidationError):
            UserCreate(
                username="testuser",
                email="not-an-email",
                password="password123"
            )
    
    def test_user_update_valid(self):
        """Валидные данные для обновления"""
        update = UserUpdate(
            city="New City",
            country="New Country",
            last_wash_date=date(2024, 1, 15),
            preferred_wash_interval=10
        )
        assert update.city == "New City"
        assert update.last_wash_date == date(2024, 1, 15)
    
    def test_user_update_partial(self):
        """Частичное обновление"""
        update = UserUpdate(city="Updated City")
        assert update.city == "Updated City"
        assert update.country is None
        assert update.last_wash_date is None
    
    def test_user_login_valid(self):
        """Валидные данные для логина"""
        login = UserLogin(
            username="testuser",
            password="password123"
        )
        assert login.username == "testuser"
        assert login.password == "password123"
    
    def test_user_response_from_model(self, test_user):
        """Создание UserResponse из модели"""
        response = UserResponse.from_orm(test_user)
        assert response.id == test_user.id
        assert response.username == test_user.username
        assert response.email == test_user.email
        assert isinstance(response.created_at, datetime)