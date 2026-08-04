# Site Monitor

Job-hunting tool that watches company careers pages, extracts vacancies, filters them against a profile and sends new ones to Telegram.

It reads structured vacancy feeds where they exist and falls back to a headless browser where they do not, so a page that renders its jobs with JavaScript still works.

---

## How it works

```
source → Vacancy → rules → Opportunity → scoring → Telegram
```

1. **Source.** For sites hosted on a known recruiting platform, the public JSON API is queried directly — no browser, and the response already carries title, location, department and a link to the posting. Everything else is loaded with Playwright, and vacancies are read from page links.
2. **Rules.** Keyword include/exclude runs first and costs nothing. Whatever it misses goes to a local LLM, with an embedding pre-filter in front of it to keep the prompt small.
3. **Storage.** Each vacancy is stored once, keyed by a fingerprint derived from its URL. A vacancy is therefore reported once, no matter how many times it is seen again.
4. **Scoring.** New vacancies are rated 1–10 against the candidate profile and sent as a digest, best first.

Supported platforms: Greenhouse, Ashby, Workable, Personio, Teamtailor, BambooHR, Pinpoint, Workday.

---

## Install

```bash
poetry install
poetry run playwright install chromium
```

Create `.env` in the project root:

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

---

## Run

```bash
poetry run python -m site_monitor.main              # loop forever
poetry run python -m site_monitor.main --once       # a single pass
poetry run python -m site_monitor.main --from-db    # re-read stored snapshots, no network
```

Useful flags:

| Flag | Effect |
|---|---|
| `--site NAME` | check only this site, repeatable |
| `--dry-run` | log results instead of sending them |
| `--min-score N` | only send vacancies scored N or higher |

**First run.** The opportunities table starts empty, so every vacancy found counts as new. Either run once with `telegram.enabled: false` to fill the database, or set `telegram.min_score`.

---

## Configuration

`site_monitor/config/settings.yaml`:

```yaml
monitor:
  interval_minutes: 480
  concurrency: 5          # sites downloaded at once
  fetch_attempts: 2       # 1 disables retries
  min_content_length: 200 # below this a page counts as not rendered
  health_alert_after: 3   # failures in a row before Telegram is warned

telegram:
  enabled: true
  min_score: 0            # 0 sends everything

ai:
  enabled: true
  base_url: http://localhost:11434
  model: qwen3.6:latest
  embedding_model: qwen3-embedding:0.6b
  concurrency: 1          # Ollama serves one request at a time
  think: false            # reasoning empties the reply on long prompts

keywords:
  roles:
    include: [account manager, customer success, business development]
    exclude: [developer, engineer, russia]
  locations: [remote, malta, cyprus]

sites:
  - name: Delasport
    url: https://job-boards.eu.greenhouse.io/delasportbulgaria
```

The AI stage is optional — with `ai.enabled: false` the tool runs on keywords alone and needs no local model.

---

## Site health

A page that fails to render is not the same as a company with no openings, so every source is tracked in `site_health`: what it returned, when it last worked, and how many runs in a row it has been failing. Bot-protection pages are recognised and recorded rather than parsed as if they were vacancy listings.

---

## Tests

```bash
poetry run pytest
```

---

## Tech

Python 3.12+, Poetry, Playwright, httpx, selectolax, SQLAlchemy + SQLite, Pydantic, loguru, tenacity, python-telegram-bot, Ollama for the local LLM.

---

## License

MIT. Free to use, modify and distribute.
