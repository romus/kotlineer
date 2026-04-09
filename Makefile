.PHONY: install install-dev build clean test lint typecheck fmt check all

# ── Setup ───────────────────────────────────────────────────────────

install:
	uv sync

install-dev:
	uv sync --extra dev

# ── Build ───────────────────────────────────────────────────────────

build:
	uv build

clean:
	rm -rf dist/ build/ .venv/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true

# ── Test ────────────────────────────────────────────────────────────

test:
	uv run python -m pytest -v

test-unit:
	uv run python -m pytest tests/ -v -k "not integration"

test-integration:
	uv run python -m pytest tests/ -v -k "integration"

# ── Quality ─────────────────────────────────────────────────────────

lint:
	uv run ruff check src/ tests/

lint-fix:
	uv run ruff check --fix src/ tests/

fmt:
	uv run ruff format src/ tests/

fmt-check:
	uv run ruff format --check src/ tests/

typecheck:
	uv run mypy src/

# ── All checks ──────────────────────────────────────────────────────

check: fmt-check lint typecheck test

all: install-dev check
