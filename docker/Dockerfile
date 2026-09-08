FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

RUN pip install --no-cache-dir uv

COPY --chown=appuser:appgroup pyproject.toml uv.lock README.md ./
COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup main.py ./

RUN uv sync --frozen --no-dev

USER appuser

EXPOSE 8000

CMD ["python", "main.py"]
