\# Site Monitor



Async website monitoring platform built with Python.



Site Monitor is a modular tool designed to automatically track websites, detect changes and notify users about important updates.



The project is built with asynchronous architecture and designed to scale from personal monitoring tasks to a production-ready monitoring platform.



\---



\## 🚀 Features



Current MVP capabilities:



\- ✅ Async website monitoring

\- ✅ Playwright browser automation

\- ✅ Single browser instance for multiple websites

\- ✅ Parallel website checks

\- ✅ YAML-based configuration

\- ✅ SQLite-based history storage

\- ✅ Modular architecture

\- ✅ Change detection



\---



\## 🏗 Architecture 



site\_monitor/



├── config/

│ └── Configuration management



├── fetchers/

│ └── Website data extraction



├── monitor/

│ └── Monitoring engine



├── parsers/

│ └── HTML processing



├── storage/

│ └── Database layer



├── notifications/

│ └── Notification system



└── main.py





\---



\## 🛠 Tech Stack



\- Python 3.12

\- Poetry

\- Playwright

\- SQLite

\- Pydantic

\- APScheduler

\- YAML



\---



\## ⚙️ Installation



\### 1. Clone repository



```bash

git clone https://github.com/username/site-monitor.git

cd site-monitor


### 2. Install dependencies

poetry install



\### 3. Install Playwright browser

poetry run playwright install chromium



\### 4. USAGE
poetry run python -m site\_monitor.main

### 5. Config
site\_monitor/config/settings.yaml

### 6. Example
sites:

&#x20; - name: Example

&#x20;   url: https://example.com



&#x20; - name: Python

&#x20;   url: https://python.org



\### 7. 🗺 Roadmap

v0.1.0 — MVP ✅



Completed:



Core monitoring engine

Browser automation

Parallel checks

Database storage

Configuration system

### 8. v0.2.0 — Rule Engine 🚧
Planned:



Keyword monitoring

CSS selector rules

XPath rules

Smart filtering

Custom triggers

### 9. v0.3.0 — Notifications
Planned:



Telegram notifications

Email alerts

Discord/Slack integration

### 10. v0.4.0 — Production Features
Planned:



Scheduler

Retry system

Docker support

Monitoring dashboard

### 11. v0.5.0 — AI Monitoring
Planned:



AI-powered change analysis

Automatic summaries

Smart relevance detection

📄 License



MIT License



Free to use, modify and distribute.


