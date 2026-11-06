from app.evaluations.internal.formatting import (
    cost_label,
    duration_label,
    join_words,
    outcome_label,
    table_header,
    table_row,
    token_usage_label,
)
from app.evaluations.internal.models import ComparedRun, ResultStatus, RunComparison


def render_comparison(comparison: RunComparison) -> str:
    original = comparison.original
    rerun = comparison.rerun
    fixed = [
        change.rule_id
        for change in comparison.rule_changes
        if change.before is ResultStatus.FAILED and change.after is ResultStatus.PASSED
    ]
    regressed = [
        change.rule_id for change in comparison.rule_changes if change.after is ResultStatus.FAILED
    ]
    other = [
        f"{change.rule_id} {change.before.value} to {change.after.value}"
        for change in comparison.rule_changes
        if change.rule_id not in fixed and change.rule_id not in regressed
    ]
    lines = (
        "## Original run compared with rerun",
        "",
        table_header("Field", "Original", "Rerun"),
        table_row("Agent version", f"`{original.agent_version}`", f"`{rerun.agent_version}`"),
        table_row("Run", f"`{original.run_id}`", f"`{rerun.run_id}`"),
        table_row("Verdict", original.verdict.value.upper(), rerun.verdict.value.upper()),
        table_row("Outcome", outcome_label(original.outcome), outcome_label(rerun.outcome)),
        table_row("Tool calls", " → ".join(original.tools), " → ".join(rerun.tools)),
        *_metric_rows(original, rerun),
        "",
        f"- Fixed rules: {join_words(fixed) or 'none'}",
        f"- Regressed rules: {join_words(regressed) or 'none'}",
        f"- Other changes: {join_words(other) or 'none'}",
    )
    return "\n".join(lines) + "\n"


def _metric_rows(original: ComparedRun, rerun: ComparedRun) -> tuple[str, ...]:
    if original.metrics is None and rerun.metrics is None:
        return ()
    rows = [
        table_row("Duration", _duration(original), _duration(rerun)),
        table_row("Token usage", _tokens(original), _tokens(rerun)),
    ]
    if _has_llm_calls(original) or _has_llm_calls(rerun):
        rows.append(table_row("LLM calls", _llm_calls(original), _llm_calls(rerun)))
    if _has_cost(original) or _has_cost(rerun):
        rows.append(table_row("Cost", _cost(original), _cost(rerun)))
    return tuple(rows)


def _duration(run: ComparedRun) -> str:
    return "not reported" if run.metrics is None else duration_label(run.metrics.duration_ms)


def _tokens(run: ComparedRun) -> str:
    if run.metrics is None:
        return "not reported"
    value = token_usage_label(
        run.metrics.total_prompt_tokens,
        run.metrics.total_completion_tokens,
        run.metrics.total_cached_tokens,
    )
    return value or "not reported"


def _has_llm_calls(run: ComparedRun) -> bool:
    return run.metrics is not None and run.metrics.llm_calls is not None


def _llm_calls(run: ComparedRun) -> str:
    return str(run.metrics.llm_calls) if _has_llm_calls(run) else "not reported"


def _has_cost(run: ComparedRun) -> bool:
    return run.metrics is not None and run.metrics.total_cost_usd is not None


def _cost(run: ComparedRun) -> str:
    return cost_label(run.metrics.total_cost_usd) if _has_cost(run) else "not reported"
