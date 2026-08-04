# Site Monitor

Асинхронный мониторинг сайтов для поиска работы: собирает вакансии с careers-страниц, фильтрует правилами и локальной LLM, шлёт оповещения в Телеграм. Проект начат совместно с ChatGPT, продолжается здесь.

## Запуск

```bash
poetry install
poetry run playwright install chromium
poetry run python -m site_monitor.main            # бесконечный цикл
poetry run python -m site_monitor.main --once     # один проход
poetry run python -m site_monitor.main --from-db  # по снимкам из БД, без сети
```

Конфиг: `site_monitor/config/settings.yaml`. Секреты — в `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).

## Архитектура

Поток: **источник → `Vacancy` → правила → `Match` → таблица `opportunities` → скоринг → Телеграм**.

- `schemas/vacancy.py` — `Vacancy` (site, title, url, location, department, source) и `fingerprint` для дедупликации: по нормализованному URL вакансии, а при его отсутствии по site+title+location
- `fetchers/ats.py` — публичные JSON API рекрутинговых платформ: greenhouse, ashby, workable, personio, teamtailor, bamboohr, pinpoint, workday. Даёт структурные поля и **прямую ссылку на вакансию** без браузера. Не распознал или API не ответил → возвращает `None`, сайт уходит в браузер
- `fetchers/playwright_fetcher.py` — один Chromium (headless), страница на каждый fetch
- `parsers/generic.py` — `parse_vacancies`: сначала ссылки `<a href>` (дают URL вакансии), при их отсутствии — фолбэк на строки текста
- `rules/keyword.py` — include/exclude по строке «title — location — department»; бонус за локацию считается по отдельному полю
- `rules/semantic.py` — LLM-классификация того, что не поймали ключевые слова; эмбеддинг-префильтр отсекает заведомо чужое. Длинные списки идут батчами по 50
- `rules/relevance.py` — оценка 1–10 под профиль кандидата, батчами по 10 вакансий за запрос
- `ai/client.py` — единая точка обращения к Ollama: один семафор на процесс, одно соединение, батчинг эмбеддингов
- `storage/` — SQLAlchemy + SQLite (`data/monitor.db`): `MonitoredPage` (снимок страницы) и `Opportunity` (найденная вакансия, уникальна по fingerprint)
- `monitor/monitor.py` — оркестратор, конвейер fetch→LLM
- `notifications/telegram.py` — дайджест, PTB v22, plain text

## Состояние (на 2026-08-04)

Ветка `main`, поверх коммита 4a9fa84. Переработаны источники данных и дедупликация:

- **ATS API**: 17 из 19 распознанных сайтов отдают вакансии напрямую, 743 вакансии за ~1 секунду без браузера. Не отдают: OpenBet (Workday закрыт, 403 «permission»), Aviatrix (доска не опубликована) — оба уходят в браузер
- **Дедупликация**: таблица `opportunities`, оповещение уходит один раз на вакансию. Повторный прогон по тем же сайтам даёт 0 новых
- **Прямые ссылки на вакансии** вместо ссылки на общую careers-страницу
- **Скорость скоринга**: 8 вакансий за 18 с вместо 140 с
- Построчный diff (`rules/diff.py::new_lines`) больше не используется — дедупликация по fingerprint заменила его. Файл остался мёртвым кодом

### Что было починено по ходу

- `/api/embed` отдавал 400 на больших списках: Ollama роняет раннер начиная примерно с 240 строк (120 проходят). Теперь батчи по 64 — падали Playtech (208), Worldpay (231), NOVOMATIC (241)
- Пустой ответ LLM (`unparseable response:` в старых логах): qwen3.6 — рассуждающая модель, уводила до 8000 символов в `thinking` и на длинном промпте не доходила до `content`. Отключено через `ai.think: false`, есть откат для моделей без поддержки флага
- `SemanticRule` обрезал список кандидатов до 50 строк и молча терял остаток — теперь батчи
- Скоринг шёл мимо семафора и конкурировал с классификацией за ту же модель — теперь семафор общий
- Telegram мог отправить пустой чанк и не резал записи длиннее лимита
- `Vacancy.fingerprint` игнорирует utm-параметры, иначе один и тот же URL давал разные отпечатки

## Известные ограничения

- Cloudflare отдаёт headless-браузеру страницу проверки вместо контента (например, Playson) — вакансии с таких сайтов не собираются
- Ссылочный режим на некоторых сайтах цепляет категории вместо вакансий (SOFTSWISS: `/expertises/account-management/`); скоринг такие обычно опускает
- GiG и другие дублируют одну роль по городам — это разные URL, поэтому разные записи и разные оповещения
- `careers.sumsub.com` — teamtailor на своём домене, детектор его не ловит и сайт идёт через браузер (работает, но медленнее)

## Не сделано (обсуждалось, отложено)

- `DATABASE_URL` захардкожен в `storage/database.py`, `config["database"]["url"]` не используется; путь относительный и зависит от cwd
- Нет health-check пустых снимков: Shift4 отдаёт 0 символов, IGT и Games Global по 13 — молча выглядит как «вакансий нет»
- Нет retry на fetch, хотя `tenacity` в зависимостях
- Нет тестов; `pytest` не в зависимостях, dev-группы в `pyproject.toml` нет
- `datetime.utcnow` в `MonitoredPage` (deprecated в 3.12); в новом коде используется `models.utcnow()`
- `README.md` весь в экранированных `\#` и описывает несуществующие фичи
- Нет argparse, флаги разбираются через `sys.argv`

## Roadmap

Цель — личный инструмент поиска работы, НЕ enterprise-платформа. Не делаем: plugin system, API, Docker, multi-user.

## Договорённости

- Poetry для зависимостей, Python 3.12+
- Логирование через loguru
- Токены/секреты не коммитить
