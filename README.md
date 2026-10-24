# Пульс бизнеса

Персональная новостная аналитика: Python 3.12, FastAPI, PostgreSQL 17, SQLAlchemy 2, Alembic. Структура backend: API → services → repositories, отдельные ORM-модели и Unit of Work. Фронтенд на React 19 и Vite подключен к OpenAPI-контракту из 25 операций.

## Быстрый запуск

Нужны Git и Docker Engine/Desktop с Compose v2.24+. До слияния PR используйте ветку реализации:

```sh
git clone -b feature/python-fullstack https://github.com/ace-593/alfa-pulse.git
cd alfa-pulse
docker compose up -d --build
```

Первый запуск собирает образы и применяет миграции. Compose сам создаёт сети и запускает сервисы в нужном порядке. Интерфейс: [localhost:8080](http://localhost:8080). Swagger UI backend: [localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs). Внешняя ссылка на API имеет тот же origin, что и фронт: `/api/v1`.

Зарегистрируйте новый аккаунт через интерфейс. По умолчанию включены три синтетические компании; доступ к ним назначается автоматически. Пароли тестовых пользователей заранее не задаются. Созданные сводки и сессии сохраняются в PostgreSQL. Ключ подписи генерируется при первом запуске и сохраняется в базе, если `SECRET_KEY` не задан.

Без настроенной LLM работают регистрация, контекст, импорт, ранжирование правилами, источники, история, оценки и трассировка. Сводка явно сообщает об отсутствии LLM, а чат возвращает `insufficient_data`. Этот режим не выдается за AI-анализ. Внешние запросы к платным моделям без настройки не выполняются.

## Настоящие данные и AI

Скопируйте `.env.example` в `.env` в корне проекта и задайте секреты приложения. Для LLM достаточно `LLM_API_KEY=ваш-командный-ключ` и `LLM_MODEL_ID=auto`: адрес шлюза организаторов и разрешённые модели уже настроены. Другие ID перечислены в `.env.example`; ключ не добавляйте в GitHub или фронтенд. Настройте `backend/data/sources.json`, загрузите CSV и назначьте доступ пользователям. Подробности: [данные и модели](docs/DATA-AND-AI.md). Все сервисы запускаются из корня проекта:

```sh
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
npm ci
npm run check
npm test
PULSE_E2E_URL=http://127.0.0.1:8080 npm test
```

Тестам backend нужна отдельная PostgreSQL-база с именем, начинающимся на `pulse_test`: они очищают ее таблицы. Без `PULSE_E2E_URL` HTTP-тест frontend пропускается; остальные проверки работают без сервера. Merge checks в PR запускают backend на PostgreSQL, собирают общий Compose-проект и выполняют HTTP-сценарий через nginx.

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
backend/app/api/v1           маршруты auth, companies, digests, materials, jobs, ingestion
backend/app/core             настройки, безопасность, зависимости и общие типы
backend/app/db               Base, фабрика сессий и Unit of Work
backend/app/models           SQLAlchemy-модели
backend/app/repositories     доступ к пользователям, сессиям и ресурсам
backend/app/schemas          OpenAPI-контракт и валидация
backend/app/services         сценарии, бизнес-правила, LLM и источники
backend/alembic              миграции
backend/tests                unit и интеграционные тесты
frontend/src                 React-компоненты, hooks и API-адаптер
frontend/public              favicon и runtime-конфигурация API
frontend/dist                результат сборки Vite (не хранится в Git)
frontend/tests               модели, сессия, API, HTTP-сценарий
deploy                       файлы сервера и обновления
docs                         документация и контракт
```

Учетные данные существуют только у этого сервиса. Интеграция с действующим интернет-банком не реализована и не требуется для запуска автономного прототипа.

## Разработка React-фронтенда

Нужен Node.js 22.12+ (или 24 LTS). API и worker запускаются общим Compose; для разработки можно запустить только их командой `docker compose up -d --build api worker`.

```sh
cd frontend
npm ci
npm run dev
```

Vite показывает локальный адрес и проксирует `/api/v1` на `http://127.0.0.1:8000`. Для другого backend: `API_UPSTREAM=http://localhost:8001 npm run dev`.

Production: `npm run build`, затем `npm start`, либо Docker Compose — Docker сам собирает React-приложение. Для `npm start` можно задать `PORT` и `API_UPSTREAM`.

Исходники: `src/App.jsx` — навигация и компоновка, `src/usePulse.js` — сессия и загрузка контекста, `src/components/` — React-компоненты, `src/lib/` — API и адаптеры данных. `public/config.js` задаёт runtime-настройки API. Токены хранятся в sessionStorage, сохранения разделены по пользователю и компании.

`npm test` запускает тесты API/адаптеров и React-компонентов; `npm run check` — production-сборку и синтаксические проверки. HTTP-тест с настоящим backend включается через `PULSE_E2E_URL`.
