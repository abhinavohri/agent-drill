# Backend quality checks

Run these commands from `backend/`:

```sh
uv run ruff check app tests
uv run python -m unittest discover -s tests -p 'test_*.py'
```

Also import `app.main`, `app.jobs.drill_mcp`, `app.jobs.ingest_trace`, `app.jobs.run_drill`, `app.jobs.evaluate_run`, and `app.jobs.build_refund_fixtures` after a structural change.

After a change to the evaluator, the refund world, a scenario, or an agent script, run `uv run python -m app.jobs.build_refund_fixtures` and commit the regenerated runs, results, and reports. A test fails when they are stale.
