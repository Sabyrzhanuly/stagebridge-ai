# Security Notes

StageBridge AI is a hackathon MVP with read-only live database analysis and a separate seeded demo dry run. Use dedicated least-privilege database users and do not expose the unauthenticated MVP API publicly.

## Implemented Controls

- Production and development profiles are opened in explicit read-only transactions.
- Statement timeout is configured on PostgreSQL sessions.
- Demo database hosts are restricted to local/Docker host names unless `ALLOW_EXTERNAL_DB_HOSTS=1`.
- Preflight SQL uses validated identifiers and `psycopg.sql` composition.
- AI output is advisory and Pydantic-validated.
- Unknown action types are rejected.
- Dry-run writes target only `stagebridge_dryrun`.
- The API never returns database passwords.
- No secrets are committed; `.env.example` contains placeholders and demo defaults only.

## Limitations

- There is no authentication or authorization layer in the MVP.
- Backend containers use Django development server settings.
- Saved connection-profile passwords are stored unencrypted at rest in the Django backend database. This is accepted only for the hackathon MVP; the API never returns them.
- Only demo-scoped controlled actions are implemented.
- The dry-run database is reset destructively by design.
- Live analyses are report-only and cannot enter the dry-run executor.
- OpenAI account, model access, retention, and compliance settings are external operational concerns.

## Production Hardening Checklist

- Add authentication, authorization, and audit logging.
- Store connection secrets in a dedicated secret manager.
- Use least-privilege PostgreSQL roles.
- Move long-running analysis into background jobs.
- Add rate limiting and request size limits.
- Expand SQL template tests with real PostgreSQL fixtures.
- Add deployment TLS and secure headers.
- Review OpenAI data handling requirements for the target organization.
