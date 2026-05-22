# Lego Collection Bot

Telegram-бот для учёта коллекции LEGO-минифигурок. Микросервисная архитектура: один PostgreSQL с разными схемами, три сервиса в Docker.

## Архитектура

```
Telegram  →  bot-service (aiogram)
                 ↓ HTTP
         ┌───────┴────────┐
         ↓                ↓
   auth-service    collection-service
   (FastAPI)       (FastAPI)
         └───────┬────────┘
                 ↓
          PostgreSQL (lego_db)
          ├── schema: auth
          └── schema: figure
```

| Сервис | Порт | Назначение |
|--------|------|------------|
| `auth-service` | 8000 | Пользователи, настройки, права доступа |
| `collection-service` | 8001 | Каталог фигурок, коллекции пользователей |
| `bot-service` | — | Telegram UI, FSM-сценарии |
| `db` | 15432 | PostgreSQL |

## Структура репозитория

```
LegoCollectionBot/
├── docker-compose.yml
├── init.sql                 # схемы auth и figure
├── .env.example
├── scripts/
│   └── bricklink_scraper.py # утилита парсинга BrickLink (не часть бота)
└── services/
    ├── auth/
    │   └── app/
    │       ├── core/        # config, db
    │       ├── models/
    │       ├── schemas/
    │       ├── crud/
    │       └── routers/
    ├── collection/
    │   └── app/
    │       ├── business/    # парсер BrickLink, коллаж (API)
    │       └── ...
    └── bot/
        └── app/
            ├── api/         # HTTP-клиенты к auth и collection
            ├── handlers/    # команды и callback-и
            ├── keyboards/
            ├── states/      # FSM
            └── services/    # коллаж для отправки в Telegram
```

## Быстрый старт

1. Скопируйте `.env.example` в `.env` и укажите `TG_TOKEN`.
2. Запустите стек:

```bash
docker compose up --build
```

3. Проверьте health:
   - http://localhost:8000/health
   - http://localhost:8001/health

4. Миграции (при первом запуске или после изменений моделей):

```bash
docker compose exec auth-service alembic upgrade head
docker compose exec collection-service alembic upgrade head
```

## Команды бота (текущий статус)

| Команда / кнопка | Статус |
|------------------|--------|
| `/start` | Регистрация; при повторном входе — главное меню |
| `/menu` | Главное меню (inline-кнопки) |
| Моя коллекция | Сводка, список, поиск, Excel, коллаж |
| Карточка фигурки | Фото, цены BrickLink, ваши записи |
| Поиск по фото | Распознавание артикула |
| Добавить | Одиночное и bulk-добавление |
| Настройки | Цены, описание, даты |
| Обновить каталог | Только admin |
| Tier-list | Коллаж по артикулам / серии |
| Тексты для BotFather | `services/bot/bot_profile.txt` |

## Переменные окружения

См. [.env.example](.env.example).

## База данных

Одна БД `lego_db`, две схемы:

- **auth** — `users`, `user_settings`, `permission_groups`
- **figure** — `figures`, `figure_to_user`, `type_of_collect`

Сервисы не дублируют БД — только разделяют схемы в PostgreSQL.

## Разработка локально

```bash
cd services/auth && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000
cd services/collection && uvicorn app.main:app --reload --port 8001
cd services/bot && python -m app.main
```

`DATABASE_URL` должен указывать на доступный PostgreSQL (локально: `localhost:15432`).
