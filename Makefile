.PHONY: check lint types test coletar api

check: lint types test

lint:
	uv run ruff check .
	uv run ruff format --check .

types:
	uv run mypy

test:
	uv run pytest -q

coletar:
	uv run mapscout

api:
	uv run uvicorn mapscout.web.app:app --reload
