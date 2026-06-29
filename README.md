# Café Cloud — Distributed Order System

Prueba técnica FullStack Developer para GAPSI.

Sistema distribuido self-contained compuesto por 3 microservicios FastAPI, 1 job de limpieza, PostgreSQL, RabbitMQ y MongoDB, orquestado con Docker Compose.

## Stack

| Componente | Tecnología |
|------------|-----------|
| Lenguaje | Python 3.12 |
| APIs | FastAPI + Pydantic v2 |
| SQL DB | PostgreSQL 16 |
| Migraciones | Alembic |
| Message Broker | RabbitMQ 3.13 (management) |
| NoSQL | MongoDB 7 |
| Scheduling | APScheduler |
| Logs | structlog JSON |
| Métricas | prometheus_client |
| Empaquetado | Poetry |
| Infra local | Docker Compose |

## Arquitectura

```text
┌──────────────┐     POST /orders        ┌─────────────────┐
│   Cliente    │ ───────────────────────>│  orders-service │
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
    │     cleanup-job     │  (cada 60s borra notificaciones >24h)
    └─────────────────────┘
```

## Requisitos previos

- Docker Engine 24+
- Docker Compose 2.20+
- (Opcional) Python 3.12 + Poetry para ejecutar tests unitarios fuera de contenedores.

## Ejecutar el sistema

```bash
# 1. Clonar el repositorio
cd cafe-cloud

# 2. Copiar variables de entorno (valores por defecto ya funcionan localmente)
cp .env.example .env

# 3. Levantar todo
docker compose up --build -d

# 4. Verificar health de los servicios
curl http://localhost:8000/health   # orders
curl http://localhost:8001/health   # processor
curl http://localhost:8002/health   # notifier
curl http://localhost:8003/health   # cleanup-job
```

> RabbitMQ Management UI: http://localhost:15672 (user/pass definidos en `.env`, por defecto `cafe` / `cafe_secret`)

## Flujo de prueba con curl

### 1. Crear una orden

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

Respuesta esperada:

```json
{
  "order_id": "<uuid>",
  "customer_id": "abc123",
  "status": "PENDING",
  "created_at": "2024-...",
  "items": [...]
}
```

### 2. Ver idempotencia

Repetir el comando anterior con el mismo `Idempotency-Key`. Debe retornar la **misma** orden sin crear un duplicado.

### 3. Consultar notificaciones

Después de ~2-5 segundos (tiempo simulado de preparación):

```bash
curl http://localhost:8002/notifications/abc123
```

Respuesta esperada:

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

### 4. Ejecutar cleanup manualmente

```bash
curl -X POST http://localhost:8003/jobs/cleanup/run
```

## Tests

### Unitarios (requieren Python 3.12 + Poetry)

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

### Integración (requiere Docker Compose levantado)

```bash
make test-integration
# o directamente:
bash scripts/integration-test.sh
```

El script valida:
- Creación de orden.
- Idempotencia con la misma `Idempotency-Key`.
- Eventual llegada de la notificación al notifier-service.

## Decisiones técnicas

### PostgreSQL + asyncpg
Elegido por transacciones ACID, soporte nativo de `RETURNING` y bloqueos pesimistas, necesarios para el patrón **Transactional Outbox** y la gestión de claves de idempotencia.

### RabbitMQ
Proporciona exchanges/colas duraderas, **publisher confirms**, **consumer acks** y **dead-letter exchanges (DLX)** nativos para retries con backoff exponencial sin implementar lógica compleja de reenvío manual.

### Transactional Outbox
Cuando se crea una orden, el evento `orders.created` se inserta en la tabla `outbox` dentro de la misma transacción. Un relay asíncrono publica los eventos pendientes en RabbitMQ y los marca como procesados. Esto garantiza consistencia entre la base de datos y el broker bajo entrega al-menos-una-vez.

### Idempotencia
- `POST /orders` requiere el header `Idempotency-Key`.
- Se valida en la misma transacción que crea la orden.
- Si la key ya existe, se retorna la orden previa sin duplicar.
- El consumer del processor verifica el estado `COMPLETED` antes de re-procesar.

### DLX / Retries
Las colas principales declaran `x-dead-letter-exchange`. Si un mensaje falla (excepción no controlada), RabbitMQ lo nack y lo envía a una cola DLX con TTL de 10s, que luego lo reinyecta vía el exchange de retry. Si el mensaje se procesa exitosamente se hace ack manual.

### Observabilidad
- Todos los servicios exponen `/health` y `/metrics`.
- Logs estructurados en JSON con `timestamp`, `level`, `service`, `trace_id`.
- El `trace_id` se genera en orders-service y se propaga por headers de mensaje y contexto de logs.

## Ejemplos de eventos

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

## Seguridad

- Credenciales y configuración vía variables de entorno (ver `.env.example`); no están hardcodeadas en el código.
- API key opcional configurada por `API_KEY`; si está presente, `GET /notifications/{customer_id}` la exige mediante header `X-API-Key`.

## Limpieza

El `cleanup-job` ejecuta cada 60 segundos una tarea que elimina notificaciones con `created_at` mayor a 24 horas. También expone `POST /jobs/cleanup/run` para ejecución manual.

## Estructura del repositorio

```text
cafe-cloud/
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

- Si un servicio no levanta, revisar logs: `docker compose logs -f <servicio>`.
- Asegurar que los puertos 5432, 5672, 15672, 27017, 8000-8003 estén libres.
- Para reiniciar desde cero: `docker compose down -v && docker compose up --build -d`.
