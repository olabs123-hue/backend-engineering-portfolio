# InfraPulse deployment notes — demonstration only

This deployment is **read-only**. It does not provide account signup or allow anonymous service registration or metric ingestion.

## One-container Docker build

From the `infra-pulse/` directory:

```bash
docker build -t infrapulse-demo .
docker run --rm -p 8000:8000 -e INFRAPULSE_CORS_ORIGINS=http://localhost:8000 infrapulse-demo
```

Open http://localhost:8000. The image builds the TypeScript frontend and serves it alongside the FastAPI endpoints from the same origin.

**Important:** Do not set `INFRAPULSE_INGEST_TOKEN` on a publicly accessible demonstration deployment. Without it, writes are denied (401). Public GET endpoints are read-only, and fresh deployments show empty monitoring data. This is intentional: no fabricated operational metrics.

## Deployment constraints

- SQLite is stored under `/tmp` in this image and **is not persistent**. Do not use this to retain important data.
- Not production-safe: no authentication for read-only endpoints, no tenant isolation, no rate limits, no retention controls, and no centralized monitoring or backups.
- Do not probe third-party sites without authorization. The collector is deliberately **not** run in the Docker image.
- To show non-empty data, run the project privately on a trusted development machine and ingest samples there using a configured secret token.
- Verify `npm run build` (or the Docker build) before calling the frontend production-ready. The hosted CI workflow checks this separately.

## Suggested validation

```bash
python -m pytest -q tests
cd frontend && npm install && npm run build
cd .. && docker build -t infrapulse-demo .
```

No public service is automatically created by this repository. Hosting accounts, networking, secrets, cost, and persistence must be reviewed before enabling a live deployment.
