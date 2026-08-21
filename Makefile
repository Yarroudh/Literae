.PHONY: install dev test lint format qdrant-up qdrant-down ingest

install:
	pip install -e ".[dev]"

dev:
	uvicorn app.api.main:app --reload

test:
	pytest -v

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

qdrant-up:
	docker compose up -d

qdrant-down:
	docker compose down

ingest:
	python scripts/ingest.py
