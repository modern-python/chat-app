# chat-app

[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen.svg)](https://github.com/modern-python/chat-app/actions/workflows/main.yml)
[![CI](https://github.com/modern-python/chat-app/actions/workflows/main.yml/badge.svg)](https://github.com/modern-python/chat-app/actions/workflows/main.yml)
[![License](https://img.shields.io/github/license/modern-python/chat-app.svg)](https://github.com/modern-python/chat-app/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/modern-python/chat-app)](https://github.com/modern-python/chat-app/stargazers)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty)

### Description

Reference chat application for the `modern-python` organisation: a
single-package Litestar service — JWT cookie auth, direct and group chats,
idempotent message send, cursor-paginated history, per-member read markers
and unread counts — built to show the org's libraries composed on a domain
more realistic than a two-table CRUD template.

## Key Features

- tests on `pytest` with automatic rollback after each test case, DI providers
  exposed as fixtures via `modern-di-pytest`
- IOC (Inversion of Control) container built on
  [modern-di](https://github.com/modern-python/modern-di/), one container for
  app- and request-scoped providers
- Observability tools integration built on
  [lite-bootstrap](https://github.com/modern-python/lite-bootstrap/)
- Linting and formatting using `ruff` and `ty`
- `Alembic` for DB migrations
- retried, use-case-owned transactions via
  [db-retry](https://github.com/modern-python/db-retry/)

### After `git clone` run

```bash
just --list
```

to see every recipe. `just run` brings up the app and Postgres in Docker
Compose and serves the API on `:8000`. `just test` cycles the database and
runs the full test suite (also via Docker Compose) at 100% coverage.

## Why this repo

`litestar-sqlalchemy-template` shows each library in isolation on a two-table
domain. Nothing shows them composed under load-bearing decisions — a
transaction that must span two writes, a unique constraint that two concurrent
requests can both hit, a count that must not cost a row per event. This repo
answers that with a domain that actually needs it. See
[PR #1](https://github.com/modern-python/chat-app/pull/1) for the full design
and `planning/decisions/` for the calls taken along the way.

| Pattern | Where to look |
|---|---|
| One DI container, app + request scopes | `app/ioc.py` |
| Use case owns the transaction boundary | `app/use_cases/create_message.py` |
| Idempotent write with a concurrent-retry fallback | `app/use_cases/create_message.py` |
| Direct-chat upsert that survives a race | `app/use_cases/create_chat.py` |
| Cursor pagination in both directions | `app/repositories/messages_repository.py` |
| Unread counts without receipt rows | `app/repositories/chats_repository.py` |
| Atomic monotonic read marker | `app/repositories/chat_members_repository.py` |
| Per-test rollback via a container override | `tests/conftest.py` |
| DI providers as pytest fixtures | `tests/use_cases/conftest.py` |
| Simulating a DB race at the repository seam | `tests/use_cases/test_create_chat.py` |

## 📝 [License](LICENSE)

## Part of `modern-python`

Browse the full list of templates and libraries in
[`modern-python`](https://github.com/modern-python) — see the org profile for the categorized index.
