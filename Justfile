default: install lint build test

down:
    docker compose down --remove-orphans

sh:
    docker compose run --service-ports api bash

test *args: down && down
    docker compose run api sh -c "sleep 1 && uv run alembic downgrade base && uv run alembic upgrade head && uv run pytest {{ args }}"

run:
    docker compose run --service-ports api sh -c "sleep 1 && uv run alembic upgrade head && uv run python -m app.api"

test-migrations *args: down && down
    docker compose run api sh -c "sleep 1 && uv run pytest tests/migrations --override-ini=addopts= {{ args }}"

migration message: && down
    # `message` is a single named parameter, shell-quoted via quote() so a multi-word message
    # survives intact - a variadic *args parameter only ever joins tokens with spaces when
    # interpolated, losing the quoting boundaries the invoking shell already stripped, so a
    # multi-word message would otherwise reach sh -c as several disconnected words.
    docker compose run api sh -c "sleep 1 && uv run alembic upgrade head && uv run alembic revision --autogenerate -m {{ quote(message) }}"

build:
    docker compose build api

install:
    uv lock --upgrade
    uv sync --all-extras --all-groups --no-install-project

lint:
    uv run eof-fixer .
    uv run ruff format .
    uv run ruff check . --fix
    uv run ty check

# Print the planning change index (flat, newest-first) to stdout.
index:
    uv run python planning/index.py

# Validate planning changes + decisions (frontmatter, lanes, spec links); CI runs this.
check-planning:
    uv run python planning/index.py --check
