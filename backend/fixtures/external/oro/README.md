# ORO preview data

This directory holds local preview rows from the public ORO Bench trajectory dataset.

Source:
`https://huggingface.co/datasets/oro-ai/orobench-trajectories`

Local files:

- `row-0.json` contains row 0 from the `trajectories` configuration and `sample` split.
- `row-0.atif.json` contains the extracted `atif_json` value from that row.

The row was retrieved on 2026-11-06 from:
`https://datasets-server.huggingface.co/rows?dataset=oro-ai%2Forobench-trajectories&config=trajectories&split=sample&offset=0&length=1`

The JSON files in this directory are ignored by Git. The dataset does not declare one
dataset-wide license. Review its usage terms before you distribute a row.

Use the preview row only to check local ATIF compatibility. Keep the synthetic fixture in
`fixtures/production_traces/` for automated tests.

Validate the local trajectory from `backend/`:

```sh
uv run python -m app.jobs.ingest_trace fixtures/external/oro/row-0.atif.json
```
