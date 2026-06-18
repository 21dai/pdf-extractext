.PHONY: up down logs ps build api db ollama help

# Paths de los compose files
COMPOSE_API=docker/docker-compose.yml
COMPOSE_DB=docker/docker-compose.db.yml
COMPOSE_OLLAMA=docker/docker-compose.ollama.yml
ENV_FILE=.env

# --- Targets principales ---

up: db ollama api
	@echo "Stack completo levantado"

api:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) up -d --build

db:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_DB) up -d

ollama:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_OLLAMA) up -d

down:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) down || true
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_OLLAMA) down || true
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_DB) down || true

logs:
	docker logs -f docker_api_1

ps:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) ps
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_OLLAMA) ps
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_DB) ps

help:
	@echo "Comandos disponibles:"
	@echo "  make up     - Levantar todo el stack (db + ollama + api)"
	@echo "  make down   - Apagar todo el stack"
	@echo "  make logs   - Ver logs de la API"
	@echo "  make ps     - Ver estado de los contenedores"
	@echo "  make api    - Levantar solo la API"
	@echo "  make db     - Levantar solo MongoDB"
	@echo "  make ollama - Levantar solo Ollama"
