# Production Deployment Evidence — Verification Status

**Status: Not independently verified.** The repository contains demonstration implementations of a payment ledger and PostgreSQL job scheduler. It is not evidence that these specific implementations are deployed in production at Sharp Technologies.

## Evidence required to substantiate deployment
- Redacted deployment or release records identifying the service, environment, deployment date, and release/commit identifier.
- CI/CD deployment job logs or change-management records showing a successful production rollout (not just tests or a build).
- A redacted production health check, monitoring dashboard, or service inventory linking the deployed service to the release.
- Company-authorized confirmation of the engineer's role and deployment scope.

Do **not** publish API keys, customer information, internal hostnames, payment data, proprietary source code, or company logs without authorization.

## Production metrics — not yet substantiated

| Metric | Verified value | Required evidence |
| --- | --- | --- |
| Production active users | Not verified | Approved analytics with definition and date range |
| Production uptime / availability | Not verified | Monitoring or SLO report with measurement window |
| Production transaction volume | Not verified | Approved aggregated transaction records with measurement window |

## Separate, reproducible engineering evidence
The repository's `benchmarks/` folder and GitHub Actions workflow document **synthetic** concurrency and recovery tests. These are not production usage, uptime, or volume statistics. See [benchmark methodology](../benchmarks/README.md).

**CV wording until production evidence is provided:** “Engineered two backend services for transactional payments and durable job scheduling using Python, FastAPI and PostgreSQL; tested concurrency and failure recovery.” Do not describe deployment as independently verified until the evidence above has been reviewed.
