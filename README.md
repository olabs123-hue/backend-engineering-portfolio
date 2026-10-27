# Backend Engineering Portfolio — Two Services

Two backend service demos maintained as part of my software engineering portfolio.

1. **ledger-service**: PostgreSQL-backed double-entry transfer API with transactional idempotency, account row locking, and a C++17 journal-validation executable.
2. **scheduler-service**: PostgreSQL durable job queue, multi-worker claiming using `FOR UPDATE SKIP LOCKED`, retries with exponential backoff, and a C++17 backoff calculator.

## Run

Install Docker Compose v2, then run each service separately.

```bash
cd ledger-service && docker compose up --build
# in another terminal:
cd scheduler-service && docker compose up --build
```

Ledger API: http://localhost:8001/docs; scheduler API: http://localhost:8002/docs.

## Quality

Each service includes Python tests, C++ unit checks, health endpoints, and GitHub Actions CI. Run `PYTHONPATH=. pytest -q` inside each service after `pip install -r requirements.txt`. Unit tests do not require a database. End-to-end concurrency and failure-recovery integration tests are future work; no throughput numbers are asserted.

## Security and limitations

Demo code only: no authentication or authorization, TLS termination, secrets manager, external payment provider integration, or production observability. Do not deploy publicly or process real money. The ledger stores integer minor currency units and checks for balanced transfer legs. The scheduler provides at-least-once processing; handlers must be idempotent. Jobs are restricted to predefined task types.
