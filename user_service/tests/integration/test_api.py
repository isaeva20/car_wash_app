import pytest
from httpx import AsyncClient
from unittest.mock import patch
import uuid

class TestHealthCheck:
    """Тесты для health check"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, app):
        """Успешный health check"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "user-service"
            assert "timestamp" in data


class TestUserRegistration:
    """Тесты для регистрации пользователя"""
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, app, clean_db):
        """Успешное создание пользователя"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            unique_id = uuid.uuid4().hex[:8]
            user_data = {
                "username": f"newuser_{unique_id}",
                "email": f"new_{unique_id}@example.com",
                "password": "testpass123",
                "city": "Moscow",
                "country": "Russia",
                "preferred_wash_interval": 7
            }
            response = await client.post("/api/users", json=user_data)
            assert response.status_code == 201, f"Response: {response.text}"
            data = response.json()
            assert data["username"] == user_data["username"]
            assert data["email"] == user_data["email"]
            assert data["city"] == user_data["city"]
            assert "id" in data
            assert "created_at" in data
            assert "password" not in data
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, app, test_user):
        """Ошибка при создании пользователя с существующим именем"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            duplicate_data = {
                "username": test_user.username,
                "email": "different@example.com",
                "password": "password123",
                "city": "City",
                "country": "Country"
            }
            response = await client.post("/api/users", json=duplicate_data)
            assert response.status_code in [400, 500], f"Response: {response.text}"
            data = response.json()
            assert "detail" in data
            detail_lower = data["detail"].lower()
            assert any(phrase in detail_lower for phrase in ["already exists", "failed to create user"])
    
    @pytest.mark.asyncio
    async def test_create_user_invalid_data(self, app):
        """Ошибка при создании пользователя с невалидными данными"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            invalid_data = {
                "username": "",
                "email": "invalid-email",
                "password": "123",
                "city": "City"
            }
            response = await client.post("/api/users", json=invalid_data)
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data


class TestAuthentication:
    """Тесты для аутентификации"""
    
    @pytest.mark.asyncio
    async def test_login_success(self, app, test_user):
        """Успешный логин"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            login_data = {
                "username": test_user.username,
                "password": "testpass123"
            }
            response = await client.post("/api/auth/login", json=login_data)
            assert response.status_code == 200, f"Response: {response.text}"
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert len(data["access_token"]) > 0
    
    @pytest.mark.asyncio
    async def test_login_wrong_password(self, app, test_user):
        """Логин с неверным паролем"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            login_data = {
                "username": test_user.username,
                "password": "wrongpassword"
            }
            response = await client.post("/api/auth/login", json=login_data)
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
            assert "incorrect" in data["detail"].lower()
    
    @pytest.mark.asyncio
    async def test_login_user_not_found(self, app):
        """Логин несуществующего пользователя"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            login_data = {
                "username": "nonexistent",
                "password": "password123"
            }
            response = await client.post("/api/auth/login", json=login_data)
            assert response.status_code == 401


class TestUserManagement:
    """Тесты для управления пользователями"""
    
    @pytest.mark.asyncio
    async def test_get_user_success(self, app, test_user):
        """Успешное получение информации о пользователе"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/api/users/{test_user.id}")
            assert response.status_code == 200, f"Response: {response.text}"
            data = response.json()
            assert data["id"] == test_user.id
            assert data["username"] == test_user.username
            assert data["email"] == test_user.email
    
    @pytest.mark.asyncio
    async def test_get_user_not_found(self, app):
        """Получение несуществующего пользователя"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            non_existent_id = "00000000-0000-0000-0000-000000000000"
            response = await client.get(f"/api/users/{non_existent_id}")
            assert response.status_code == 404
    
    
    @pytest.mark.asyncio
    async def test_update_user_success(self, app, test_user, valid_token):
        """Успешное обновление пользователя"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {valid_token}"}
            update_data = {
                "city": "Updated City",
                "country": "Updated Country"
            }
            response = await client.put(
                f"/api/users/{test_user.id}",
                json=update_data,
                headers=headers
            )
            assert response.status_code == 200, f"Response: {response.text}"
            data = response.json()
            assert data["city"] == "Updated City"
            assert data["country"] == "Updated Country"
            assert data["username"] == test_user.username
    
    @pytest.mark.asyncio
    async def test_update_user_unauthorized(self, app, valid_token):
        """Попытка обновить другого пользователя"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {valid_token}"}
            unique_id = uuid.uuid4().hex[:8]
            other_user_data = {
                "username": f"otheruser_{unique_id}",
                "email": f"other_{unique_id}@example.com",
                "password": "password123",
                "city": "City"
            }
            create_response = await client.post("/api/users", json=other_user_data)
            assert create_response.status_code == 201
            other_user_id = create_response.json()["id"]
            update_data = {"city": "Hacked City"}
            response = await client.put(
                f"/api/users/{other_user_id}",
                json=update_data,
                headers=headers
            )
            assert response.status_code == 403
    
    @pytest.mark.asyncio
    async def test_update_wash_date_success(self, app, test_user, valid_token):
        """Успешное обновление даты мойки"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {valid_token}"}
            wash_date = "2024-01-15"
            response = await client.put(
                f"/api/users/{test_user.id}/wash-date?wash_date={wash_date}",
                headers=headers
            )
            assert response.status_code == 200, f"Response: {response.text}"
            data = response.json()
            assert data["last_wash_date"] == wash_date
    
    @pytest.mark.asyncio
    async def test_update_wash_date_invalid_date(self, app, test_user, valid_token):
        """Обновление даты мойки с невалидной датой"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {valid_token}"}
            invalid_date = "not-a-date"
            response = await client.put(
                f"/api/users/{test_user.id}/wash-date?wash_date={invalid_date}",
                headers=headers
            )
            assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_get_all_users(self, app, test_user, valid_token):
        """Получение списка всех пользователей"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {valid_token}"}
            response = await client.get("/api/users", headers=headers)
            assert response.status_code == 200, f"Response: {response.text}"
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 1
            user_ids = [user["id"] for user in data]
            assert test_user.id in user_ids


class TestErrorHandling:
    """Тесты обработки ошибок"""
    
    @pytest.mark.asyncio
    async def test_invalid_token(self, app, test_user):
        """Доступ с невалидным токеном"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": "Bearer invalid.token.here"}
            update_data = {"city": "New City"}
            response = await client.put(
                f"/api/users/{test_user.id}",
                json=update_data,
                headers=headers
            )
            assert response.status_code == 401, f"Response: {response.text}"
    
    @pytest.mark.asyncio
    async def test_expired_token(self, app, test_user, expired_token):
        """Доступ с просроченным токеном"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {expired_token}"}
            update_data = {"city": "New City"}
            response = await client.put(
                f"/api/users/{test_user.id}",
                json=update_data,
                headers=headers
            )
            assert response.status_code == 401, f"Response: {response.text}"
    
    @patch("app.main.CRUD.get_user_by_id")
    @pytest.mark.asyncio
    async def test_database_error(self, mock_get_user, app, valid_token):
        """Ошибка базы данных"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            mock_get_user.side_effect = Exception("Database connection failed")
            headers = {"Authorization": f"Bearer {valid_token}"}
            
            response = await client.get(
                "/api/users/some-id",
                headers=headers
            )
            assert response.status_code == 500, f"Response: {response.text}"
            data = response.json()
            assert "error" in data or "detail" in data