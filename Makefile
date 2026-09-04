.PHONY: up down logs test lint seed reset fresh

up:            ## Build and start everything
	docker compose up --build

down:
	docker compose down

reset:         ## Wipe the database and storage, then start clean
	docker compose down -v && docker compose up --build

logs:
	docker compose logs -f api

test:
	cd backend && python -m pytest -q

lint:
	cd backend && ruff check app tests
	cd cms && npx tsc --noEmit
	cd viewer && npx tsc --noEmit
