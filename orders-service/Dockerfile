FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==1.8.3

COPY shared/ /shared/
COPY orders-service/pyproject.toml orders-service/poetry.lock* /app/
COPY orders-service/alembic.ini /app/alembic.ini
COPY orders-service/alembic /app/alembic
COPY orders-service/orders_service /app/orders_service

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --only main --no-root

FROM python:3.12-slim AS runtime

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app /app

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn orders_service.main:app --host 0.0.0.0 --port 8000"]
