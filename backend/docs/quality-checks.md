# Backend quality checks

Run these commands from `backend/`:

```sh
.venv/bin/ruff check app tests
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
```

Also import `app.main` and `app.jobs.drill_mcp` after a structural change.

