# StageBridge AI Devpost Submission

## Project Name

StageBridge AI

## Elevator Pitch

StageBridge AI validates whether production PostgreSQL data can safely load into a staging database using a newer development schema.

## Inspiration

Schema drift often looks harmless until real production rows hit new constraints, enum changes, foreign keys, or type casts. Teams need a fast way to find blocking data issues before a staging refresh fails halfway through.

## What It Does

StageBridge AI inspects production and development PostgreSQL schemas, detects supported drift categories deterministically, runs read-only preflight checks against production data, asks OpenAI or a mock provider for a structured remediation plan, lets a human approve controlled actions, and executes an isolated dry run.

## How We Built It

- Django 5 and Django REST Framework for the backend API.
- psycopg 3 for PostgreSQL catalog inspection, preflight checks, and dry-run execution.
- Pydantic for strict internal and AI response models.
- OpenAI Python SDK with the Responses API for structured advisory plans.
- Vue 3, TypeScript, Vite, Pinia, Vue Router, Axios, and lucide icons for the frontend.
- Docker Compose and PostgreSQL 17 for repeatable demo databases.

## Challenges

- Keeping AI advisory while making schema detection deterministic.
- Safely rendering SQL from controlled templates instead of model-generated SQL.
- Building a real dry-run path while keeping the hackathon scope honest.
- Making the UI understandable within a short live demo.

## Accomplishments

- Six deterministic conflict types are implemented.
- The mock provider keeps the full demo working without an API key.
- The dry run resets an isolated database, applies the development schema, loads raw production rows, applies approved transformations, and records validation logs.
- The UI presents database topology, conflicts, approvals, dry-run progress, and final metrics.

## What We Learned

Schema compatibility is as much about production data as it is about DDL. AI is useful for summarizing and ordering remediation decisions, but the detection and execution layers need deterministic guardrails.

## What's Next

- Support arbitrary schema loading and larger databases.
- Add background jobs for long-running checks.
- Add secure connection profile management.
- Expand action templates and conflict coverage.
- Add team approvals and audit exports.

## Built With

PostgreSQL, Python, Django, Django REST Framework, psycopg, Pydantic, OpenAI Responses API, Vue, TypeScript, Vite, Pinia, Vue Router, Axios, Docker Compose.

## Suggested Image Gallery

- Dashboard topology and metrics.
- Conflict detail panel with preflight evidence.
- AI recommendation and controlled action approvals.
- Dry-run timeline and final report.
- Architecture diagram.

## Three-Minute Video Script

1. Show the dashboard and explain the production, development, and dry-run databases.
2. Run analysis and show six conflicts.
3. Open conflict detail evidence for invalid numeric price and duplicate email.
4. Generate the AI or mock plan and point out structured advisory output.
5. Approve controlled actions and show SQL previews.
6. Run the dry run and show passed status, transferred rows, rejected rows, and zero validation failures.

