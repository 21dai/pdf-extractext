.PHONY: up down logs ps api tp-up tp-down benchmark test calidad help

# Compose de desarrollo: una instancia de la API, sin base de datos (ADR-0008)
COMPOSE_API=docker/docker-compose.yml
ENV_FILE=.env

# --- Targets principales ---

up: api

api:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) up -d --build

down:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) down

logs:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) logs -f api

ps:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) ps

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
	@echo "  make up     - Levantar la API de desarrollo (igual que make api)"
	@echo "  make down   - Apagar la API de desarrollo"
	@echo "  make logs   - Ver logs de la API"
	@echo "  make ps     - Ver estado del contenedor"
	@echo "  make api    - Levantar la API en el puerto local"
	@echo "  make tp-up    - Levantar el stack del TP (Traefik + 5 replicas)"
	@echo "  make tp-down  - Apagar el stack del TP"
	@echo "  make benchmark - Spike y Vegeta contra el profesor (Windows)"
	@echo "  make test     - Tests con cobertura minima del 95 %"
	@echo "  make calidad  - black, isort, flake8 y mypy"
