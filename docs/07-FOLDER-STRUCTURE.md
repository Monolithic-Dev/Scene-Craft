# SceneCraft — Enterprise Folder Structure

> Read `00-INDEX.md` first for how this fits into the full documentation set. Hand this file to Claude Code first when scaffolding the repo.

```
scenecraft/
├── apps/
│   ├── web/                        # Next.js frontend (control plane UI)
│   │   ├── app/                    # App Router pages
│   │   ├── components/             # Reusable UI components (shadcn-based)
│   │   ├── lib/                    # API client, auth helpers
│   │   └── public/
│   └── api/                        # FastAPI backend (control plane)
│       ├── src/
│       │   ├── main.py             # App entrypoint — middleware, exception handling, router mounting
│       │   ├── api/                 # Route handlers (versioned: v1/)
│       │   ├── core/                # Config, security, database session, exceptions
│       │   ├── models/              # SQLAlchemy ORM models
│       │   ├── schemas/             # Pydantic request/response schemas
│       │   ├── services/            # Business logic (auth service, project service)
│       │   └── repositories/        # Data access layer (repository pattern — services never touch the ORM directly)
│       └── tests/
├── agents/
│   ├── orchestrator/               # LangGraph graph definition, Coordinator agent
│   ├── breakdown_agent/
│   ├── frame_agent/
│   ├── app_build_agent/
│   ├── critic_agent/
│   ├── iteration_agent/
│   └── shared/                     # Shared prompt templates, schemas, MCP client
├── mcp_server/                     # Internal MCP server exposing project-state tools to agents
├── infra/
│   ├── terraform/                  # IaC: Cloud Run, Cloud SQL, Pub/Sub, IAM
│   └── docker/                     # Dockerfiles per service
├── .github/workflows/              # CI/CD pipelines
├── docs/                           # This documentation set, plus judge guide + demo script when written
└── scripts/                        # Dev/setup scripts
```

## Rationale per top-level folder

- **`apps/`** — the product's control plane (auth, project CRUD, UI). Deliberately separated from `agents/` so each half of the system can be built, tested, and scaled independently. This split is itself a signal of architectural maturity worth calling out in your judge-facing docs.
- **`agents/`** — the agentic pipeline. One subfolder per agent from `04-AGENT-ARCHITECTURE.md`, plus `orchestrator/` for the graph that sequences them and `shared/` for anything more than one agent needs (prompt templates, the MCP client, common schemas) — don't duplicate this across agent folders.
- **`mcp_server/`** — a standalone package, not buried inside `agents/`, because it's a genuine service boundary: agents are MCP *clients*, this is the MCP *server*. Keeping it separate makes that boundary visible in the repo layout, not just in prose.
- **`infra/`** — infrastructure-as-code lives with the application code, versioned and reviewed the same way. No infrastructure change should ever be made by hand in the GCP console without a corresponding Terraform diff.
- **`docs/`** — this file set. Keep it in the repo, not in a separate wiki — a judge (or a future contributor) should find the full spec one `cd docs` away from the code it describes.

## Rules for using this structure with Claude Code

1. Scaffold folders before files — an empty `agents/critic_agent/` with just an `__init__.py` is a better starting point than deciding file names on the fly mid-session.
2. Never let a file grow to hold more than one responsibility described in `09-CODING-STANDARDS.md` — if `services/project_service.py` starts doing what `repositories/project_repository.py` should do, that's a signal to split it back apart, not a shortcut worth taking.
3. Tests live next to what they test in structure (`apps/api/tests/` mirrors `apps/api/src/`), not in a separate top-level `tests/` folder disconnected from the code.
