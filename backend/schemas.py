from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionEvent(BaseModel):
    """
    Canonical transaction event.

    Required fields:
        event_id
        timestamp
        source
        user_id
        amount

    Optional fields:
        category
        description
        merchant
        status
        email
        phone

    email and phone are included specifically for the
    identity-mismatch edge case.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1)
    timestamp: datetime
    source: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    amount: float

    category: Optional[str] = None
    description: Optional[str] = None
    merchant: Optional[str] = None
    status: Optional[str] = None

    email: Optional[str] = None
    phone: Optional[str] = None


class UserState(BaseModel):
    """
    Persisted unified state for one user.

    This is a storage/data model only.
    Identity-resolution decisions happen in the pipeline.
    """

    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(..., min_length=1)

    txn_count_24hr: int = 0
    average_amount_30d: Optional[float] = None

    email: Optional[str] = None
    phone: Optional[str] = None

    last_event_id: Optional[str] = None
    last_updated: Optional[datetime] = None


class ProcessingDecision(BaseModel):
    """
    Persisted decision for one event.
    """

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., min_length=1)

    decision_reason: str
    model_label: Optional[str] = None
    model_score: Optional[float] = None

    is_duplicate: bool = False
    is_late: bool = False

    config_json: Optional[str] = None
    processed_at: datetime


class IngestResponse(BaseModel):
    """
    JSON response contract for POST /ingest.
    """

    event_id: str
    status: str
    decision: str
    reason: str