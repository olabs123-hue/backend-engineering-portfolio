# Featured Engineering Projects

**Portfolio focus:** Full-Stack & Distributed Systems Engineering

This guide groups representative repositories by the engineering problems they demonstrate. It does not claim that every project is publicly deployed or production-ready.

| Project | Domain | Stack | Evidence and scope |
| --- | --- | --- | --- |
| [LedgerFlow](https://github.com/olabs123-hue/LedgerFlow.) | Full-stack financial ledger simulation | React, FastAPI, PostgreSQL | Public browser-local showcase; transactional operations tested in isolated CI, not publicly enabled |
| [SentinelAI](https://github.com/olabs123-hue/SentinelAI) | Security event dashboard | FastAPI, SQLite, browser UI | Local defensive hackathon MVP; rule-based detection, not trained AI |
| [Distributed Event Processing](https://github.com/olabs123-hue/distributed-event-processing) | Streaming and reliability | C++17, Kafka, PostgreSQL, Docker | Idempotent persistence and failure testing; benchmark scopes documented separately |
| [AtlasKV](https://github.com/olabs123-hue/AtlasKV-Transactional-Database) | Database internals | C++17, CMake | Educational transactional storage engine, not production/distributed database |
| [Autonomous Network Reliability](https://github.com/olabs123-hue/autonomous-network-reliability) | Network automation | Python, FRRouting, Containerlab | Simulation/lab topology with tests; measured recovery only where raw evidence exists |

## Suggested GitHub profile pin order

1. LedgerFlow — showcase UI + transaction correctness
2. SentinelAI — browser dashboard + API
3. Distributed Event Processing — streaming systems
4. AtlasKV — database internals
5. Autonomous Network Reliability — networking and observability
6. Backend Engineering Portfolio — ledger and scheduler service demos

## Recruiter walkthrough

Start with [LedgerFlow's public showcase](https://ledgerflow-showcase-olabs123.onrender.com), then inspect its [architecture](https://github.com/olabs123-hue/LedgerFlow./blob/main/docs/ARCHITECTURE.md) and tests. Review SentinelAI to see event-to-dashboard functionality; continue with Distributed Event Processing and AtlasKV for lower-level systems engineering.

## Profile README installation

The neighboring [PROFILE_README.md](PROFILE_README.md) contains the intended GitHub profile overview. GitHub renders it on the profile only after a **public repository named exactly `olabs123-hue`** (owned by the account `olabs123-hue`) is created and the text is placed in that repository's root `README.md`.
