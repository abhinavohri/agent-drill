from app.evaluations.internal.formatting import join_words, outcome_label, table_header, table_row
from app.evaluations.internal.models import ResultStatus, RunComparison


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
        "",
        f"- Fixed rules: {join_words(fixed) or 'none'}",
        f"- Regressed rules: {join_words(regressed) or 'none'}",
        f"- Other changes: {join_words(other) or 'none'}",
    )
    return "\n".join(lines) + "\n"
