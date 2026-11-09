# PostgreSQL benchmark (synthetic, isolated)

Run the `postgres-benchmarks` GitHub Actions workflow. It creates disposable PostgreSQL 16 databases, starts the actual FastAPI ledger Docker image (including the C++ journal validator), and exercises the actual scheduler worker's `claim` and `complete` functions.

The ledger benchmark sends 100 unique concurrent transfer requests from 10 clients, then 10 requests with the same idempotency key. It checks committed transfer counts, double-entry journal balance and conserved account balances. The scheduler benchmark enqueues 100 jobs and uses 10 concurrent worker threads to claim and complete them, checking attempt counts and duplicate claims. A separate test simulates lease expiry, reclaims the job and verifies that the old claim token cannot complete it.

**Limitations:** This is a small synthetic correctness/throughput smoke benchmark on shared GitHub-hosted hardware, not production performance. The scheduler benchmark calls the real claim/complete functions, but does not run the infinite worker loop, execute external job side effects or kill a worker process. Its failure test simulates an expired lease, not a process crash. Results are valid only if the workflow succeeds; inspect the downloadable `postgres-benchmark-results` JSON artifact and Actions logs. The benchmark does not establish exactly-once external side effects.

No existing application files are modified by this benchmark.
