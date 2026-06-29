# Cafe Cloud — Distributed Order System

Technical test for a FullStack Developer role at GAPSI.

A self-contained distributed system made of 3 FastAPI microservices, 1 cleanup job, PostgreSQL, RabbitMQ, and MongoDB, orchestrated with Docker Compose.

## Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| APIs | FastAPI + Pydantic v2 |
| SQL DB | PostgreSQL 16 |
| Migrations | Alembic |
| Message Broker | RabbitMQ 3.13 (management) |
| NoSQL | MongoDB 7 |
| Scheduling | APScheduler |
| Logs | structlog JSON |
| Metrics | prometheus_client |
| Packaging | Poetry |
| Local infra | Docker Compose |

## Architecture

```text
┌──────────────┐     POST /orders        ┌─────────────────┐
│   Client     │ ───────────────────────>│  orders-service │
└──────────────┘   Idempotency-Key       └────────┬────────┘
                                                  │
                                                  │ Transactional Outbox
                                                  │ (orders.created)
                                                  ▼
                                          ┌───────────────┐
                                          │  PostgreSQL   │
                                          │  + outbox     │
                                          └───────┬───────┘
                                                  │
                                                  │ Outbox Publisher
                                                  ▼
                                          ┌───────────────┐
                                          │    RabbitMQ   │
                                          │  events topic │
                                          └───────┬───────┘
                                                  │
              ┌───────────────────────────────────┘
              │
              ▼
    ┌─────────────────────┐     orders.completed      ┌─────────────────┐
    │  processor-service  │ ─────────────────────────>│ notifier-service│
    └─────────────────────┘                           └────────┬────────┘
                                                               │
                                                               ▼
                                                       ┌───────────────┐
                                                       │    MongoDB    │
                                                       │ notifications │
                                                       └───────┬───────┘
                                                               │
              ┌────────────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────┐
    │     cleanup-job     │  (every 60s deletes notifications >24h old)
    └─────────────────────┘
```

## Prerequisites

- Docker Engine 24+
- Docker Compose 2.20+
- (Optional) Python 3.12 + Poetry to run unit tests outside containers.

## Running the system

```bash
# 1. Clone the repository
cd gapsi-challenge-2

# 2. Copy environment variables (defaults already work locally)
cp .env.example .env

# 3. Start everything
docker compose up --build -d

# 4. Verify service health
curl http://localhost:8000/health   # orders
curl http://localhost:8001/health   # processor
curl http://localhost:8002/health   # notifier
curl http://localhost:8003/health   # cleanup-job
```

> RabbitMQ Management UI: http://localhost:15672 (user/pass are defined in `.env`, default `cafe` / `cafe_secret`)

## Test flow with curl

### 1. Create an order

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: demo-key-123" \
  -d '{
    "customer_id": "abc123",
    "items": [
      {"name": "latte", "qty": 1},
      {"name": "muffin", "qty": 2}
    ]
  }'
```

Expected response:

```json
{
  "order_id": "<uuid>",
  "customer_id": "abc123",
  "status": "PENDING",
  "created_at": "2024-...",
  "items": [...]
}
```

### 2. Verify idempotency

Repeat the command above with the same `Idempotency-Key`. It must return the **same** order without creating a duplicate.

### 3. Query notifications

After ~2-5 seconds (simulated preparation time):

```bash
curl http://localhost:8002/notifications/abc123
```

Expected response:

```json
[
  {
    "order_id": "<uuid>",
    "customer_id": "abc123",
    "message": "Your order <uuid> is ready for pickup!",
    "created_at": "2024-..."
  }
]
```

### 4. Run cleanup manually

```bash
curl -X POST http://localhost:8003/jobs/cleanup/run
```

## Tests

### Unit tests (require Python 3.12 + Poetry)

```bash
poetry -C orders-service install
poetry -C orders-service run pytest -q

poetry -C processor-service install
poetry -C processor-service run pytest -q

poetry -C notifier-service install
poetry -C notifier-service run pytest -q

poetry -C cleanup-job install
poetry -C cleanup-job run pytest -q
```

### Integration test (requires Docker Compose running)

```bash
make test-integration
# or directly:
bash scripts/integration-test.sh
```

The script validates:
- Order creation.
- Idempotency with the same `Idempotency-Key`.
- Eventual delivery of the notification to the notifier-service.

## Technical decisions

### PostgreSQL + asyncpg
Chosen for ACID transactions, native `RETURNING` support, and pessimistic locking, required for the **Transactional Outbox** pattern and idempotency-key management.

### RabbitMQ
Provides durable exchanges/queues, **publisher confirms**, **consumer acks**, and native **dead-letter exchanges (DLX)** for exponential backoff retries without complex manual redelivery logic.

### Transactional Outbox
When an order is created, the `orders.created` event is inserted into the `outbox` table within the same transaction. An async relay publishes pending events to RabbitMQ and marks them as processed. This guarantees consistency between the database and the broker under at-least-once delivery.

### Idempotency
- `POST /orders` requires the `Idempotency-Key` header.
- It is validated inside the same transaction that creates the order.
- If the key already exists, the previous order is returned without duplication.
- The processor consumer checks the `COMPLETED` status before re-processing.

### DLX / Retries
Main queues declare `x-dead-letter-exchange`. If a message fails (unhandled exception), RabbitMQ nacks it and sends it to a DLX queue with a 10s TTL, which then re-injects it via the retry exchange. Successful messages are manually acked.

### Observability
- All services expose `/health` and `/metrics`.
- Structured JSON logs with `timestamp`, `level`, `service`, `trace_id`.
- `trace_id` is generated in orders-service and propagated through message headers and log context.

## Event examples

### `orders.created`

```json
{
  "order_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "customer_id": "abc123",
  "items": [
    {"name": "latte", "qty": 1},
    {"name": "muffin", "qty": 2}
  ],
  "status": "PENDING",
  "created_at": "2024-01-01T12:00:00+00:00"
}
```

### `orders.completed`

```json
{
  "order_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
  "customer_id": "abc123",
  "status": "COMPLETED",
  "completed_at": "2024-01-01T12:00:05+00:00"
}
```

## Security

- Credentials and configuration are provided via environment variables (see `.env.example`); they are not hardcoded in the code.
- Optional API key configured through `API_KEY`; when present, `GET /notifications/{customer_id}` requires it via the `X-API-Key` header.

## Cleanup

The `cleanup-job` runs every 60 seconds a task that deletes notifications with `created_at` older than 24 hours. It also exposes `POST /jobs/cleanup/run` for manual execution.

## Repository structure

```text
gapsi-challenge-2/
├── docker-compose.yml
├── Makefile
├── README.md
├── .env.example
├── scripts/
│   └── integration-test.sh
├── shared/
│   └── shared/
│       ├── config.py
│       ├── db.py
│       ├── health.py
│       ├── logging_config.py
│       ├── messaging.py
│       └── models.py
├── orders-service/
├── processor-service/
├── notifier-service/
└── cleanup-job/
```

## Troubleshooting

- If a service does not start, check the logs: `docker compose logs -f <service>`.
- Make sure ports 5432, 5672, 15672, 27017, 8000-8003 are free.
- To restart from scratch: `docker compose down -v && docker compose up --build -d`.
