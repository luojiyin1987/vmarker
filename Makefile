.PHONY: format check test install clean help

format:
	uv run ruff format .
	uv run ruff check --fix .

check:
	uv run ruff check .

test:
	uv run pytest

install:
	uv pip install -e ".[dev]"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

help:
	@echo "Available commands:"
	@echo "  make format  - Format code with ruff"
	@echo "  make check   - Run linting"
	@echo "  make test    - Run tests"
	@echo "  make install - Install in dev mode"
	@echo "  make clean   - Clean cache files"
	@echo "  make help    - Show this help message"
