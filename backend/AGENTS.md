# Backend agent rules

These rules apply to all files in `backend/`.

## Documentation

- Read [docs/README.md](docs/README.md) before a structural change.
- Update the matching document when a change alters a shared backend rule.
- Keep process entry-point paths stable unless the task includes deployment changes.

## Structure

- Use direct domain packages under `app/`.
- Give each domain package one public `facade.py` file.
- Put private domain code in the domain's `internal/` package.
- Import another domain through its `facade.py` file.
- Do not import another domain's `internal/` package.
- Keep `app/main.py` limited to application assembly and process lifecycle work.
- Keep `app/jobs/` as the stable process entry-point package.

## Responsibilities

- A route validates HTTP input and maps the result to an HTTP response.
- A facade defines the public operations and types of one domain.
- An internal service owns business logic.
- A provider client owns one external API or protocol contract.
- A parser converts untrusted source data into validated application data.

## Change rules

- Add code to an existing domain before you create a new domain.
- Give workflows and packages names that describe their purpose.
- Add a facade export only when another domain needs it.
- Do not use a facade for imports inside the same domain.
- Keep validation at each external input boundary.
- Add a focused test for new branching, parsing, identity matching, or policy logic.
- Search callers, tests, configuration, and exports before you move or delete code.
- Delete dead code, empty source directories, and generated cache directories.
- Do not commit `__pycache__` or compiled Python files.

## Data models

- Use a Pydantic model for HTTP input, HTTP output, provider responses, and stable workflow contracts.
- Use a dataclass for typed internal state that does not need runtime validation or serialization.
- Use a dictionary only for dynamic key sets or direct wire serialization.
- Validate untrusted data once at the boundary.
- Pass validated models through internal code.

## Validation

Run these commands from `backend/`:

```sh
.venv/bin/ruff check app tests
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Import `app.main` and each `app.jobs.*` entry point after a structural change.
Run a live `/health` check when the backend is available.

