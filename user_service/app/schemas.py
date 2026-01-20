from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import date, datetime


class HealthCheck(BaseModel):
    """Схема для health check"""
    status: str
    service: str
    database: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None

class UserBase(BaseModel):
    username: str
    email: EmailStr
    city: Optional[str] = None
    country: Optional[str] = "Unknown"

class UserCreate(UserBase):
    """Схема для создания пользователя"""
    password: str = Field(..., min_length=6, description="Пароль должен быть не менее 6 символов")
    preferred_wash_interval: int = Field(7, ge=1, le=14) 

    @validator('username')
    def validate_username(cls, v):
        if not v or len(v.strip()) > 20:
            raise ValueError('Имя пользователя не должно содержать более 20 символов')
        return v.strip()
    
    @validator('password')
    def validate_password(cls, v):
        if ' ' in v:
            raise ValueError('Пароль не должен содержать пробелы')
        if len(v) < 6:
            raise ValueError('Пароль должен быть не менее 6 символов')
        return v

class UserUpdate(BaseModel):
    city: Optional[str] = None
    country: Optional[str] = None
    last_wash_date: Optional[date] = None
    preferred_wash_interval: Optional[int] = Field(None, ge=1, le=14)


class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(UserBase):
    id: str
    last_wash_date: Optional[date] = None
    preferred_wash_interval: int = 14
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None
