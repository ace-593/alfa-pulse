# Архитектура

Backend организован по образцу [AB-testing-platform](https://github.com/AnastasiaYuhimenko/AB-testing-platform/tree/52149df9510aa2a712ce474a5daf74dd8317a1b4/app). Использована структура каталогов и разделение обязанностей; код и предметная модель другого проекта не переносятся.

```text
app/
  api/v1/         auth, companies, digests, materials, jobs, ingestion
  core/           config, security, bootstrap, dependencies, entities, exceptions
  db/             base, session, unit_of_work
  models/         users, sessions, resources
  repositories/   user_repo, session_repo, resource_repo
  schemas/        contracts
  services/       auth_service, catalog_service, analytics_service, jobs_service,
                  ingestion_service, quality_service, llm_service, source_service,
                  common, policies, ports
  main.py         FastAPI, lifespan, ошибки, журналирование и healthcheck
  worker.py       обработка фоновых задач
  manage.py       команды оператора
  quality.py      отчёт качества
```

Маршруты вызывают сервисы, сервисы работают через Unit of Work и репозитории. SQLAlchemy-модели находятся в `models`, SQL-запросы — в `repositories`, управление транзакциями — в `db/unit_of_work.py`. `db/base.py` содержит общую ORM metadata, `db/session.py` — фабрику сессий. `core/dependencies.py` собирает одинаковые зависимости для API и worker; worker не импортирует FastAPI-приложение. Общие типы и ошибки не зависят от HTTP или ORM, бизнес-правила находятся в `services/policies.py`.

`api/v1/router.py` объединяет отдельные маршрутизаторы. `api/v1/common.py` связывает каждый обработчик с operationId существующего OpenAPI-контракта, валидирует запрос и выполняет аутентификацию через общую зависимость. Статусы, заголовки, URL и схемы данных сохранены. `schemas/contracts.py` использует прежний `backend/data/openapi.json`; параллельные копии DTO не вводятся.

Состояние сессий, версий материалов, задач, сводок, диалогов и обратной связи сохраняется в PostgreSQL. Фоновые задачи исполняет worker с атомарным захватом записи. Клиент опрашивает `/jobs`, а затем загружает неизменяемый результат.

Фронтенд — React 19 и Vite. `App.jsx` отвечает за навигацию и компоновку, `usePulse.js` — за сессию, контекст и жизненный цикл запросов. Компоненты в `src/components/` отображают авторизацию, ленту, историю, профиль и разбор события с чатом. API-адаптер в `src/lib/` работает с контрактом `/api/v1`; пользовательские основания, банковская аналитика и трассировка берутся с сервера. React экранирует текст материалов, внешние ссылки ограничены HTTP(S), запросы отменяются при смене контекста и закрытии разбора.

Production-сборка Vite создаёт `frontend/dist/`, который не хранится в Git. Docker сначала выполняет `npm ci` и `npm run build`, затем отдаёт артефакты через nginx. Локальная разработка: `npm run dev` с прокси к backend. Сохранения разделены по пользователю и компании; токены остаются в sessionStorage.

SQLAlchemy-модели авторизации находятся в `models/users.py` и `models/sessions.py`. Аналитические агрегаты хранятся версионируемыми JSONB-документами с индексом; это сохраняет изменяемые снимки схемы без привязки сервисных типов к ORM, но не заменяет специализацию таблиц при росте нагрузки. Все изменения сервиса проходят через асинхронный Unit of Work. Конкурентные операции с сессиями, идемпотентностью, импортом и бюджетом используют транзакционные advisory locks. Worker захватывает запись через `FOR UPDATE SKIP LOCKED`, продлевает lease и проверяет его перед публикацией результата.

HTTP-адаптер валидирует запросы по единому OpenAPI-файлу и переводит прикладные ошибки в согласованные ответы. Дублирующий набор Pydantic DTO не поддерживается параллельно с контрактом; соответствие ответов проверяется интеграционными тестами. OpenAPI отдается самим API и хранится в репозитории в YAML/JSON.

Выборы сверены с официальными руководствами: [FastAPI JWT/Argon2](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [отдельная AsyncSession для задач SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), [Alembic](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [зависимости готовности Compose](https://docs.docker.com/compose/how-tos/startup-order/).

Рефакторинг структуры не меняет таблицы, индексы, JSONB-документы или ревизию Alembic `001`; повторный импорт данных не требуется. Docker продолжает запускать `app.main:app` и `python -m app.worker`, весь проект поднимается корневым Compose.
