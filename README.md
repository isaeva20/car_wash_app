*Технические аспекты проекта Car wash app:*
**Архитектура**

Микросервисная архитектура с 3 сервисами:
1. Wash Advisor Service (Сервис рекомендаций)
2. User Service (Сервис пользователей)
   Аутентификация/авторизация (JWT)
   Управление профилями пользователей
3. Weather Service (Сервис погоды)
   Интеграция с внешними API погоды
**Используемые технологии:**

Backend:
  Python 3.13 + FastAPI
  SQLAlchemy 2.0 + asyncpg/aiosqlite
  Pydantic v2
  JWT
  Pytest + pytest-asyncio
  Pytest-cov
Базы данных:
  PostgreSQL
  SQLite (тестирование)
Контейнеризация:
  Docker + Docker Compose





