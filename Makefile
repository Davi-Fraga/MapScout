.PHONY: check lint types test coletar api

check: lint types test

lint:
	uv run ruff check .
	uv run ruff format --check .

types:
	uv run python -m mypy

test:
	uv run python -m pytest -q

coletar:
	uv run python -m mapscout.cli coletar $(ARGS)

api:
	uv run python -m uvicorn mapscout.web.app:app --reload --host 127.0.0.1 --port 8000
