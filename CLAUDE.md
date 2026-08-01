# Site Monitor

Асинхронный мониторинг сайтов для поиска работы: парсит страницы по тегам/ключевым словам и шлёт оповещения в Телеграм. Проект начат совместно с ChatGPT, продолжается здесь.

## Запуск

```bash
poetry install
poetry run playwright install chromium
poetry run python -m site_monitor.main
```

Конфиг: `site_monitor/config/settings.yaml` (сайты, интервал, телеграм-токен).

## Архитектура

- `fetchers/playwright_fetcher.py` — один браузер Chromium (headless), страница на каждый fetch
- `parsers/generic.py` — selectolax, пока извлекает только `<title>`
- `monitor/monitor.py` — оркестратор: fetch → parse → сравнение с БД, параллельность через Semaphore(3)
- `storage/` — SQLAlchemy + SQLite (`data/monitor.db`), модель `MonitoredPage`
- `rules/` — движок правил (в разработке): `engine.py` прогоняет правила, каждое правило имеет метод `check(site, url, old_content, new_content)` и возвращает `OpportunityEvent` или None
- `notifications/` — пусто, здесь будет Телеграм

## Состояние (на 2026-08-01)

- v0.1.0 MVP готов и закоммичен (тег v0.1.0)
- Ветка `feature/opportunity-engine`: реализован полный v0.2-pipeline (не закоммичено):
  - `parsers/generic.py::parse_text` — извлечение чистого текста страницы
  - `storage` — колонка `content` в `monitored_pages` (снимок текста)
  - `rules/diff.py::new_lines` — новые/изменённые строки между снимками
  - `rules/keyword.py::KeywordRule` — include/exclude фильтр, отдаёт `OpportunityEvent`
  - `notifications/telegram.py::TelegramNotifier` — PTB v22, plain text, лимит 4000 символов
  - `main.py` — бесконечный цикл с интервалом из настроек
- Ключевые слова в `settings.yaml` (профиль: Account Manager / Customer Success / BizDev)
- Секреты в `.env` (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) — файл создан с заглушками, пользователь должен заполнить
- Телеграм выключен (`telegram.enabled: false`) пока нет токена; без notifier события пишутся в лог
- Пустые заготовки: `rules/date.py`, `rules/relevance.py` — для будущих версий

## Roadmap (скорректирован пользователем 2026-08-01)

Цель — личный инструмент поиска работы, НЕ enterprise-платформа. Не делаем пока: plugin system, AI scoring, API, Docker, multi-user.

- v0.2 — рабочий pipeline: diff → keywords → Telegram ← СДЕЛАНО, ждёт токена и коммита
- Дальше: реальные careers-страницы в `sites`, планировщик/retry, потом AI-анализ (openai уже в зависимостях)

## Договорённости

- Poetry для зависимостей, Python 3.12+
- Логирование через loguru
- Токены/секреты не коммитить — телеграм-токен через .env или settings.yaml (в .gitignore)
