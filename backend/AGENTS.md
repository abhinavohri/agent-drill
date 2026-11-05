# Backend agent rules

These rules apply to all files in `backend/`.

## Documentation

- Read [docs/README.md](docs/README.md) before a structural change.
- Update the matching document when a change alters a shared backend rule.

## Repository layout

- Keep temporary cross-team input records in `fixtures/stubs/` until the shared contracts replace them.
- Keep production-trace samples in `fixtures/production_traces/`. Remove secrets and customer data first.
- The simulation runtime records live run events. The evaluation workstream owns production-trace ingestion and conversion to scenarios.

## Change rules

- Delete dead code and empty source directories. Do not commit generated caches or compiled Python files.

## Validation

Run these commands from `backend/`:

```sh
uv run ruff check app tests
uv run python -m unittest discover -s tests -p 'test_*.py'
```

Import `app.main` and each `app.jobs.*` entry point after a structural change.
Run a live `/health` check when the backend is available.

