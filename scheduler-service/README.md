# Distributed Job Scheduler Demo

Run `docker compose up --build` and open http://localhost:8002/docs. The Compose file starts two workers. POST `/jobs` with `{ "kind":"sum", "payload":{"numbers":[1,2,3]}, "max_attempts":3 }`, then GET `/jobs/{id}`.

PostgreSQL is the durable queue. `FOR UPDATE SKIP LOCKED` prevents workers claiming the same row concurrently; leases allow recovery after a worker dies. Retries use a C++17 bounded exponential backoff calculator. This is **at-least-once**, not exactly-once. For long-running tasks, lease renewal and fencing would be required; demo tasks finish quickly. Result persistence, authentication, metrics, graceful shutdown, and a dead-letter replay endpoint are future improvements.
