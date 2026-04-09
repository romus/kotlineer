.PHONY: install install-dev build clean test lint typecheck fmt check all pipx-install pipx-uninstall

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

test: install-dev
	uv run python -m pytest -v

test-unit: install-dev
	uv run python -m pytest tests/ -v -k "not integration"

test-integration: install-dev
	uv run python -m pytest tests/ -v -k "integration"

# ── Quality ─────────────────────────────────────────────────────────

lint: install-dev
	uv run ruff check src/ tests/

lint-fix: install-dev
	uv run ruff check --fix src/ tests/

fmt: install-dev
	uv run ruff format src/ tests/

fmt-check: install-dev
	uv run ruff format --check src/ tests/

typecheck: install-dev
	uv run mypy src/

# ── Local install ──────────────────────────────────────────────────

pipx-install: build
	pipx install dist/*.whl --force

pipx-uninstall:
	pipx uninstall kotlineer

# ── All checks ──────────────────────────────────────────────────────

check: fmt-check lint typecheck test

all: install-dev check
