# Projects

Some of Levon's work is under NDA, so these are the projects he can show.

## NFT Mini Apps (Telegram, 2024–2026)
Bots and Mini Apps with NFT assets and Telegram Gifts. Payments through TON Wallet, Telegram Wallet, MetaMask and Crypto Pay. Asset state and notifications flow through Kafka. About 50k users, 1M events a day, four payment rails. Stack: Node.js, Kafka, MongoDB, TON.

## ArmadaBoost (marketplace, 2024–2026)
Game-boosting marketplace with about 100k monthly active users. Orders, Stripe and PayPal payments, cashback and the admin panel. The frontend was moved to TypeScript. Stack: Laravel, Vue 3, Pinia, PostgreSQL.

## SwanLab AI (AI automation, 2026)
An AI request manager for a lab equipment supplier. It reads client emails and attachments (Excel, PDF, Word), prices items from the price list and the quote archive, replies in the same thread with a PDF quote, emails the supplier and follows up, then issues POs and contract specs from the client's templates. Stack: Python, LLM, IMAP, PostgreSQL.

## Finder (expert marketplace, 2024–2026)
A Fiverr-style platform: expert profiles, questions, articles and projects, reviews and real-time chat. Consultations and mentoring are booked and held over video on the site (Zoom SDK), with funds held in a wallet until the order is done, plus deposits and withdrawals. Stack: Next.js, Laravel 11, Horizon, React Query.

## Yavvi.ai (AI studio, 2026)
The web side of a computer-vision studio for factories and warehouses: dashboards, admin panels, REST APIs. LLMs are plugged into internal workflows: about 40% less manual work, API p95 under 200 ms, weekly releases. Stack: Laravel, Nuxt, Redis, LLM.

## Policy Gateway (AI infrastructure, 2026)
An OpenAI-compatible gateway in front of LLM providers. It checks client keys, runs requests through configurable regex policies, stores matches in PostgreSQL and passes the upstream response through untouched, SSE streams included. Supports /v1/chat/completions and /v1/responses, with an admin panel for rules and logs. Stack: FastAPI, React, PostgreSQL, Caddy.

## Konvey (B2B catalog, 2025–2026)
Industrial equipment catalog and ordering for B2B. A system catalog plus client catalogs, custom fields per product, cart and checkout with magic-link sign-in, files and drawings attached to items. Stack: Laravel 12, Vue 3, Inertia, Spatie.

## Telego (Telegram + AI, 2025–2026)
Project management inside Telegram: an admin bot plus a separate bot per project, all in one asyncio process. Scheduled standups and deadlines, reports, and answers from project documents (RAG), DWG and DXF drawings included. Stack: Python, aiogram 3, FAISS, PostgreSQL.

## Vestige Bot (open source, 2026)
A Telegram Business bot that keeps deleted, edited and view-once messages. Source code: github.com/manch1915/vestige-bot. MIT license. Stack: Python, aiogram 3, Telegram Business API.

## alpha-wis.com (fintech, 2025)
Investment platform on Yii2: investor accounts, calculations and the admin side. Stack: PHP, Yii2, MySQL.

# Проекты

Часть работ под NDA, поэтому здесь то, что можно показать.

- NFT Mini Apps (2024–2026): боты и Mini Apps с NFT и Telegram Gifts, оплата через TON Wallet, Telegram Wallet, MetaMask и Crypto Pay, состояния и уведомления через Kafka. Около 50 тысяч пользователей, миллион событий в день.
- ArmadaBoost (2024–2026): маркетплейс игрового бустинга, около 100 тысяч активных пользователей в месяц, платежи Stripe и PayPal, кэшбэк, админка, перевод фронта на TypeScript.
- SwanLab AI (2026): ИИ-менеджер заявок для поставщика лабораторного оборудования. Читает письма и вложения, считает цену по прайсу и архиву котировок, отправляет КП в PDF, пишет поставщику, выпускает PO и спецификации.
- Finder (2024–2026): маркетплейс экспертов в духе Fiverr с видеоконсультациями на Zoom SDK, чатами в реальном времени и кошельком с удержанием средств.
- Yavvi.ai (2026): веб-часть студии компьютерного зрения, дашборды, админки, REST API, LLM во внутренних процессах.
- Policy Gateway (2026): OpenAI-совместимый шлюз перед LLM-провайдерами с regex-политиками, логами в PostgreSQL и проксированием SSE.
- Konvey (2025–2026): B2B-каталог промышленного оборудования с клиентскими каталогами и входом по magic link.
- Telego (2025–2026): управление проектами в Telegram, бот на каждый проект в одном процессе, RAG по документации, разбор DXF-чертежей.
- Vestige Bot (2026): open source Telegram Business-бот, сохраняет удалённые и отредактированные сообщения.
- alpha-wis.com (2025): инвестиционная платформа на Yii2.
