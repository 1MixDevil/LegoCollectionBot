# Lego Collection Bot

Telegram-бот для учёта коллекции LEGO-минифигурок. Микросервисная архитектура: один PostgreSQL с разными схемами, три сервиса в Docker.

## Архитектура

```
Telegram  →  bot-service (aiogram, лёгкий)
                 │  HTTP                    Celery task
                 ↓                          ↓
         auth / collection              redis
                 ↓                          ↓
          PostgreSQL              celery-worker
                                  (сборка коллажей)
```

| Сервис | Порт | Назначение |
|--------|------|------------|
| `bot-service` | — | Telegram UI, FSM; коллажи **только в очередь** |
| `celery-worker` | — | Сборка tier-list / коллажей, отправка файла в чат |
| `redis` | 6379 (внутри Docker) | Очередь Celery |
| `auth-service` | 8000 | Пользователи, настройки, права |
| `collection-service` | 8001 | Каталог, коллекции |
| `db` | 15432 | PostgreSQL |

### VPS 4 GB — расклад памяти (ориентир)

| Компонент | RAM (лимит Docker) |
|-----------|-------------------|
| `celery-worker` | ~1536 MB |
| `postgres` | ~512 MB |
| `bot` + `auth` + `collection` | ~896 MB |
| `redis` | ~192 MB |
| **Итого Docker** | **~3.1 GB** |
| ОС + MTProxy/VLESS (вне compose) | **~0.7–1 GB** |

Коллаж **не грузит процесс бота** → нет `Start polling` при сборке 100+ фигурок.

### Сколько пользователей выдержит сервер

| Метрика | Оценка |
|---------|--------|
| Зарегистрированные пользователи | **500+** (бот только отвечает на сообщения) |
| Одновременно в чате (кнопки, карточки) | **50–100** без проблем |
| **Коллажи одновременно** | **1** (`CELERY_WORKER_CONCURRENCY=1`) |
| Коллажей в час (100 фиг., ~3 части) | **~15–25** |
| Очередь: 5 коллажей подряд | последний ждёт **~15–25 мин** |

Рекомендация: при росте нагрузки сначала поднять `CELERY_WORKER_CONCURRENCY=2` и `CELERY_MEM_LIMIT=2g` (нужен запас на VPS), не увеличивать concurrency бота.

**Почему не 2 воркера на 4 GB:** два коллажа по ~100 фигурок = два пика RAM → риск OOM. Один воркер + очередь — предсказуемо.

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
docker compose up -d --build
docker compose ps
docker compose logs -f celery-worker bot-service
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
| Tier-list | Коллаж в фоне (Celery), результат в чат |
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
# отдельный терминал — воркер коллажей:
cd services/bot && celery -A app.celery_app worker -Q collage -c 1 --loglevel=info
```

`DATABASE_URL` должен указывать на доступный PostgreSQL (локально: `localhost:15432`).  
Локально нужен Redis (`CELERY_BROKER_URL=redis://localhost:6379/0`).
