.PHONY: up down logs ps build api db limpiar-carga tp-up tp-down benchmark test calidad help

# Paths de los compose files
COMPOSE_API=docker/docker-compose.yml
COMPOSE_DB=docker/docker-compose.db.yml
ENV_FILE=.env

# --- Targets principales ---

up: db api
	@echo "Stack completo levantado"

api:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) up -d --build

db:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_DB) up -d

down:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) down || true
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_DB) down || true

logs:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) logs -f api

ps:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) ps
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_DB) ps

# Proceso de administracion (12-Factor XII): borra lo que dejan las pruebas de carga
limpiar-carga:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) exec api python -m app.admin.clear_documents --name-regex "^(carga vu|vegeta)"

# --- Stack del TP (docker-compose.yml de la raiz): Traefik + 5 replicas ---

tp-up:
	docker compose up --build -d

tp-down:
	docker compose --profile monitoreo down

# Benchmark completo contra el profesor (spike de k6 y Vegeta)
benchmark:
	powershell -NoProfile -ExecutionPolicy Bypass -File tests/stress/benchmark.ps1

# --- Calidad (lo mismo que el CI) ---

test:
	uv run pytest -q --cov=app --cov-fail-under=95

calidad:
	uv run black --check app tests main.py
	uv run isort --check-only app tests main.py
	uv run flake8 app tests main.py
	uv run mypy app main.py

help:
	@echo "Comandos disponibles:"
	@echo "  make up     - Levantar todo el stack (db + api)"
	@echo "  make down   - Apagar todo el stack"
	@echo "  make logs   - Ver logs de la API"
	@echo "  make ps     - Ver estado de los contenedores"
	@echo "  make api    - Levantar solo la API"
	@echo "  make db     - Levantar solo MongoDB"
	@echo "  make limpiar-carga - Borrar los documentos de las pruebas de carga"
	@echo "  make tp-up    - Levantar el stack del TP (Traefik + 5 replicas)"
	@echo "  make tp-down  - Apagar el stack del TP"
	@echo "  make benchmark - Spike y Vegeta contra el profesor (Windows)"
	@echo "  make test     - Tests con cobertura minima del 95 %"
	@echo "  make calidad  - black, isort, flake8 y mypy"
