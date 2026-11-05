"""Temporary scenario fixture boundary."""

import json
from pathlib import Path

from app.refunds.internal.models import RefundScenario


def load_refund_scenario(path: Path) -> RefundScenario:
    # shortcut: local fixtures replace shared Scenario records, remove this loader when contracts land.
    return RefundScenario.model_validate(json.loads(path.read_text()))
