# syntax=docker/dockerfile:1

# --- Etapa 1: construir el entorno virtual con uv --------------------------
FROM python:3.14-slim AS builder

# Binario oficial de uv, solo en esta etapa: la imagen final no lo necesita.
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv

# Bytecode precompilado (arranque mas rapido, 12-Factor IX) y copias reales
# en vez de links, para poder mover el .venv a la imagen final.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Primero solo las dependencias: esta capa se reutiliza mientras no cambie
# uv.lock, aunque cambie el codigo.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY main.py ./

# --- Etapa 2: imagen final, sin uv ni herramientas de build ---------------
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

# Usuario sin privilegios (principio de menor privilegio).
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

COPY --from=builder --chown=appuser:appgroup /app /app

USER appuser

EXPOSE 8000

CMD ["python", "main.py"]
