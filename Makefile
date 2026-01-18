.PHONY: dev ingest dev-all

dev:
	poetry run python -m backend.app.main

ingest:
	poetry run python scripts/spa.py ingest

dev-all:
	bash scripts/dev.sh
