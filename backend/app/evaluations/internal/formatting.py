import json
from collections.abc import Iterable, Mapping

from pydantic import JsonValue

from app.workflows.facade import Outcome


def money(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def outcome_label(outcome: Outcome | None) -> str:
    if outcome is None:
        return "none, because the run did not complete"
    return outcome.value.replace("_", " ")


def outcomes_label(outcomes: Iterable[Outcome]) -> str:
    return " or ".join(outcome_label(outcome) for outcome in outcomes)


def call_label(tool: str, arguments: Mapping[str, JsonValue]) -> str:
    rendered = ", ".join(f"{key}={compact_json(value)}" for key, value in arguments.items())
    return f"{tool}({rendered})"


def compact_json(value: JsonValue, limit: int = 0) -> str:
    text = json.dumps(value, ensure_ascii=False)
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def join_words(items: Iterable[str]) -> str:
    values = list(items)
    if len(values) < 2:
        return "".join(values)
    return f"{', '.join(values[:-1])} and {values[-1]}"


def duration_label(duration_ms: int) -> str:
    return f"{duration_ms / 1000:.2f} s"


def cost_label(cost_usd: float) -> str:
    return f"${cost_usd:.6f}"


def token_usage_label(prompt: int | None, completion: int | None, cached: int | None) -> str:
    values = (
        (prompt, "prompt"),
        (completion, "completion"),
        (cached, "cached"),
    )
    return ", ".join(f"{value:,} {label}" for value, label in values if value is not None)


def table_row(*cells: str) -> str:
    escaped = (cell.replace("|", "\\|").replace("\n", " ") for cell in cells)
    return f"| {' | '.join(escaped)} |"


def table_header(*titles: str) -> str:
    return "\n".join((table_row(*titles), table_row(*("---" for _ in titles))))
