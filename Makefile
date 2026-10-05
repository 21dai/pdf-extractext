.PHONY: up down logs ps build api db limpiar-carga help

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
	docker logs -f docker_api_1

ps:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) ps
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_DB) ps

# Proceso de administracion (12-Factor XII): borra lo que dejan las pruebas de carga
limpiar-carga:
	docker compose --env-file $(ENV_FILE) -f $(COMPOSE_API) exec api python -m app.admin.clear_documents --name-regex "^(carga vu|vegeta)"

help:
	@echo "Comandos disponibles:"
	@echo "  make up     - Levantar todo el stack (db + api)"
	@echo "  make down   - Apagar todo el stack"
	@echo "  make logs   - Ver logs de la API"
	@echo "  make ps     - Ver estado de los contenedores"
	@echo "  make api    - Levantar solo la API"
	@echo "  make db     - Levantar solo MongoDB"
	@echo "  make limpiar-carga - Borrar los documentos de las pruebas de carga"
