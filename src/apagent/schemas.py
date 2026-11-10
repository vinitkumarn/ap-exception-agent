"""Pydantic models = the contract. If the model's output doesn't fit, we reject it."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RootCause = Literal[
    "INSUFFICIENT_DATA", "DUPLICATE_EXACT", "DUPLICATE_POSSIBLE", "QTY_OVER_ORDERED",
    "QTY_OVER_RECEIVED", "PRICE_OVER_TOLERANCE", "SMALL_PRICE_VARIANCE", "NO_ISSUE",
]
Route = Literal["PROCUREMENT", "RECEIVING", "AP", "NONE"]
NextStep = Literal[
    "INVESTIGATE_MISSING_DATA", "REJECT_DUPLICATE", "REVIEW_POSSIBLE_DUPLICATE",
    "REQUEST_CORRECTED_INVOICE", "CONFIRM_RECEIPT", "CONFIRM_PRICE_WITH_BUYER",
    "REVIEW_SMALL_VARIANCE", "NO_ACTION",
]
Status = Literal["SUGGESTION", "NEEDS_HUMAN"]


class Suggestion(BaseModel):
    """What the agent hands to the AP analyst. Never an action, only a suggestion."""
    model_config = ConfigDict(extra="forbid")

    invoice_id: str
    root_cause: RootCause
    route_to: Route
    next_step: NextStep
    status: Status
    explanation: str = Field(min_length=20, max_length=1500)
    evidence: list[str] = Field(min_length=1, max_length=12)
    needs_human_reason: str | None = None

    @model_validator(mode="after")
    def reason_required_for_human(self):
        if self.status == "NEEDS_HUMAN" and not self.needs_human_reason:
            raise ValueError("needs_human_reason is required when status is NEEDS_HUMAN")
        return self


class Expected(BaseModel):
    root_cause: RootCause
    route_to: Route
    next_step: NextStep
    status: Status


class Case(BaseModel):
    """One labeled eval case. The label comes from what the generator SEEDED, not from the rules."""
    case_id: str
    invoice_id: str
    tags: list[str]
    expected: Expected
    note: str = ""
