"""Typed scenarios created for one ad hoc drill."""

from typing import Annotated, Literal

from pydantic import Field

from app.refunds.facade import RefundScenarioSeed
from app.workflows.internal.models import Identifier, LibraryModel


class DirectEnvironment(LibraryModel):
    kind: Literal["direct"] = "direct"


AdHocEnvironment = Annotated[
    DirectEnvironment | RefundScenarioSeed,
    Field(discriminator="kind"),
]


class AdHocScenario(LibraryModel):
    id: Identifier
    task: str = Field(min_length=1)
    environment: AdHocEnvironment
