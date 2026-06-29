.PHONY: up down build logs test test-integration seed clean

up:
	docker compose up --build -d

down:
	docker compose down -v

build:
	docker compose build

logs:
	docker compose logs -f

test:
	poetry -C orders-service run pytest -q
	poetry -C processor-service run pytest -q
	poetry -C notifier-service run pytest -q
	poetry -C cleanup-job run pytest -q

test-integration:
	bash scripts/integration-test.sh

seed:
	poetry -C orders-service run python ../scripts/seed.py

clean:
	docker compose down -v
	docker system prune -f
