# Transactional Payment & Ledger Demo

`docker compose up --build` starts PostgreSQL and the API on port 8001. Open `/docs` for request examples.

Example workflow: create two accounts with opening balances 10000 and 0, then POST `/transfers` with `{ "from_id":1,"to_id":2,"amount":125,"idempotency_key":"transfer-0001" }`. Repeating the same request returns `replayed: true`; reusing the key with a different payload returns 409. Transfers lock accounts in deterministic order and write balanced journal legs atomically. `/reconcile` checks journal sums, not opening balances. This is a demo; there is no external payment-provider integration or real-money handling.
