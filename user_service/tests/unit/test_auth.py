import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from jose import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import create_access_token, get_current_user


class TestAuth:
    """Тесты для модуля аутентификации"""
    
    def test_create_access_token_success(self):
        """Успешное создание JWT токена"""
        test_data = {"sub": "testuser", "user_id": "123"}
        token = create_access_token(test_data)
        assert isinstance(token, str)
        assert len(token) > 0
        payload = jwt.decode(
            token, 
            "test-secret-key-for-testing-only", 
            algorithms=["HS256"]
        )
        assert payload["sub"] == "testuser"
        assert payload["user_id"] == "123"
        assert "exp" in payload
    
    def test_create_access_token_with_custom_expiry(self):
        """Создание токена с кастомным временем жизни"""
        test_data = {"sub": "testuser"}
        custom_expiry = timedelta(minutes=60)
        token = create_access_token(test_data, expires_delta=custom_expiry)
        payload = jwt.decode(
            token,
            "test-secret-key-for-testing-only",
            algorithms=["HS256"]
        )
        exp_time = datetime.fromtimestamp(payload["exp"])
        time_diff = exp_time - datetime.utcnow()
        assert time_diff > timedelta(minutes=30)
    
    @patch("app.auth.logger")
    def test_create_access_token_logging(self, mock_logger):
        """Проверка логирования при создании токена"""
        test_data = {"sub": "loggeduser"}
        mock_logger.info.assert_called_once_with(
            f"Token created for user: {test_data['sub']}"
        )
    
    @pytest.mark.asyncio
    @patch("app.auth.jwt.decode")
    async def test_get_current_user_success(self, mock_jwt_decode):
        """Успешное получение пользователя из токена"""
        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "valid.token.here"
        
        expected_payload = {
            "sub": "testuser",
            "user_id": "123",
            "exp": datetime.utcnow().timestamp() + 3600
        }
        mock_jwt_decode.return_value = expected_payload
        result = await get_current_user(mock_credentials)
        assert result == {
            "username": "testuser",
            "user_id": "123"
        }
        mock_jwt_decode.assert_called_once_with(
            "valid.token.here",
            "test-secret-key-for-testing-only",
            algorithms=["HS256"]
        )
    
    @pytest.mark.asyncio
    @patch("app.auth.jwt.decode")
    async def test_get_current_user_missing_username(self, mock_jwt_decode):
        """Ошибка при отсутствии username в токене"""
        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "invalid.token"
        
        mock_jwt_decode.return_value = {"user_id": "123"}
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    @patch("app.auth.jwt.decode")
    async def test_get_current_user_missing_user_id(self, mock_jwt_decode):
        """Ошибка при отсутствии user_id в токене"""
        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "invalid.token"
        
        mock_jwt_decode.return_value = {"sub": "testuser"}
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    @patch("app.auth.jwt.decode")
    async def test_get_current_user_jwt_error(self, mock_jwt_decode):
        """Ошибка декодирования JWT токена"""
        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "invalid.token"
        
        mock_jwt_decode.side_effect = jwt.JWTError("Invalid token")
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token_structure(self):
        """Тест с некорректной структурой токена"""
        mock_credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        mock_credentials.credentials = "not-a-valid-jwt-token"
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(mock_credentials)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED