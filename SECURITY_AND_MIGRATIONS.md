# Security and migration notes

- `SCHEDULER_API_KEY` must be a random secret of at least 32 characters. Supply `Authorization: Bearer <secret>` to job endpoints. Do not commit secrets.
- Set `JWT_SECRET` to a random value (at least 32 characters). Terminate TLS at a trusted proxy, rate-limit login and registration, and add audit logs and token revocation before production.
- SQL scripts under `migrations/` distinguish fresh installations from legacy upgrades. Do not run fresh-install scripts blindly against existing databases.
- Existing ledger accounts require audited opening-balance backfill. Missing opening balances should be treated as reconciliation mismatches.
- Runtime schema creation is not a substitute for a migration runner such as Alembic.
- Scheduler processing is at-least-once. Fencing protects status updates, not external side effects; use idempotent handlers.
- Live PostgreSQL integration tests and CI must pass before claiming production readiness.
