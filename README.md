# Пульс бизнеса

Персональная новостная аналитика: Python 3.12, FastAPI, PostgreSQL 17, SQLAlchemy 2, Alembic. Луковая архитектура. Фронтенд на HTML/CSS/JS из предоставленного архива подключен к нашему OpenAPI-контракту из 25 операций.

## Быстрый запуск

Нужны Git и Docker Engine/Desktop с Compose v2.24+. До слияния PR используйте ветку реализации:

```sh
git clone -b feature/python-fullstack https://github.com/AnastasiaYuhimenko/alfa-pulse.git
cd alfa-pulse
docker compose -f backend/compose.yaml up -d
docker compose -f frontend/compose.yaml up -d
```

Первый запуск собирает образы и применяет миграции. Backend создает общую сеть, поэтому запускается первым. Интерфейс: [localhost:8080](http://localhost:8080). Swagger UI backend: [localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs). Внешняя ссылка на API имеет тот же origin, что и фронт: `/api/v1`.

Зарегистрируйте новый аккаунт через интерфейс. По умолчанию включены три синтетические компании; доступ к ним назначается автоматически. Пароли тестовых пользователей заранее не задаются. Созданные сводки и сессии сохраняются в PostgreSQL. Ключ подписи генерируется при первом запуске и сохраняется в базе, если `SECRET_KEY` не задан.

Без настроенной LLM работают регистрация, контекст, импорт, ранжирование правилами, источники, история, оценки и трассировка. Сводка явно сообщает об отсутствии LLM, а чат возвращает `insufficient_data`. Этот режим не выдается за AI-анализ. Внешние запросы к платным моделям без настройки не выполняются.

## Настоящие данные и AI

Скопируйте `backend/.env.example` в `backend/.env`, задайте секреты и параметры разрешенного провайдера. Настройте `backend/data/sources.json`, загрузите CSV и назначьте доступ пользователям. Подробности: [данные и модели](docs/DATA-AND-AI.md). Затем запускайте Compose из соответствующих каталогов, чтобы `.env` читался однозначно:

```sh
cd backend
docker compose up -d --build
cd ../frontend
docker compose up -d --build
```

Содержимое банковских отчетов и реальные клиентские CSV не включены в репозиторий. Синтетические данные не подтверждают экспертную позицию банка. При отсутствии оригинального отчета блок позиции банка остается пустым с пояснением.

## Проверки

```sh
cd backend
uv sync --frozen
TEST_DATABASE_URL=postgresql+asyncpg://pulse:password@127.0.0.1:5432/pulse_test uv run pytest -q
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
cd ../frontend
npm run check
npm test
PULSE_E2E_URL=http://127.0.0.1:8080 npm test
```

Тестам backend нужна отдельная PostgreSQL-база с именем, начинающимся на `pulse_test`: они очищают ее таблицы. Без `PULSE_E2E_URL` HTTP-тест frontend пропускается; остальные проверки работают без сервера. Merge checks в PR запускают backend на PostgreSQL, собирают оба Docker-проекта и выполняют HTTP-сценарий через nginx.

## Документация

- [Архитектура и границы слоев](docs/ARCHITECTURE.md)
- [OpenAPI YAML](docs/openapi.yaml), [JSON](docs/openapi.json)
- [API и сценарий интеграции](docs/API.md)
- [Данные, парсер, агент и бюджет](docs/DATA-AND-AI.md)
- [Развертывание, обновление и резервные копии](docs/DEPLOYMENT.md)
- [Проверка критериев ТЗ](docs/ACCEPTANCE.md)
- [Результаты проверок](docs/TESTING.md)
- [Сторонние компоненты](THIRD_PARTY_NOTICES)

## Структура

```text
backend/app/domain           сущности и правила
backend/app/application      сценарии и порты
backend/app/infrastructure   PostgreSQL, JWT, источники, LLM
backend/app/presentation     HTTP и валидация OpenAPI
backend/alembic              миграции
backend/tests                unit и интеграционные тесты
frontend/dist                интерфейс и API-адаптер
frontend/tests               модели, сессия, API, HTTP-сценарий
deploy                       файлы сервера и обновления
docs                         документация и контракт
```

Учетные данные существуют только у этого сервиса. Интеграция с действующим интернет-банком не реализована и не требуется для запуска автономного прототипа.
