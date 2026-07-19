# Architecture

StageBridge AI is a monorepo with a Django REST backend, Vue frontend, Docker Compose infrastructure, and repeatable PostgreSQL demo databases.

## Backend

The backend lives in `backend/` and is split into small service modules:

- `schema_inspector.py` queries PostgreSQL catalogs and normalizes metadata.
- `diff_engine.py` performs deterministic schema comparison.
- `preflight.py` runs read-only production data checks with safe identifier composition.
- `ai_provider.py` calls OpenAI Responses API or the deterministic mock provider and validates the response with Pydantic.
- `actions.py` enforces the controlled action allowlist.
- `dry_run.py` resets `stagebridge_dryrun`, applies the development schema, loads raw production rows, applies approved transformations, validates constraints, and records logs.

Persisted Django models:

- `AnalysisRun`
- `Conflict`
- `RemediationPlan`
- `ApprovedAction`
- `DryRunLog`

## Data Flow

```mermaid
sequenceDiagram
  participant UI as Vue UI
  participant API as Django API
  participant Prod as Production DB
  participant Dev as Development DB
  participant AI as OpenAI or Mock
  participant Dry as Dry-run DB

  UI->>API: POST /api/analysis/run/
  API->>Prod: Inspect schema and run preflight checks
  API->>Dev: Inspect schema
  API->>API: Persist conflicts
  UI->>API: POST /api/analysis/{id}/ai-plan/
  API->>AI: Structured conflict payload
  AI-->>API: Strict remediation plan
  API->>API: Persist allowlisted actions
  UI->>API: PATCH approvals
  UI->>API: POST /api/analysis/{id}/dry-run/
  API->>Dry: Reset and apply development schema
  API->>Prod: Read source rows
  API->>Dry: Load raw rows and apply templates
  API->>Dry: Validate constraints
  API-->>UI: Final report
```

## Frontend

The frontend lives in `frontend/` and uses Vue 3, TypeScript, Vite, Pinia, Vue Router, Axios, and lucide icons. It includes:

- dashboard metrics;
- database topology;
- connection overview;
- new analysis entry point;
- conflict list and detail panel;
- AI recommendation panel;
- action approval controls;
- dry-run timeline;
- final report metrics.

## Infrastructure

`docker-compose.yml` starts:

- PostgreSQL 17 with seeded demo databases;
- Django backend on port `8000`;
- Vite preview frontend on port `5173`.

The PostgreSQL initialization script is `infrastructure/postgres/init/001-create-demo-databases.sql`.

