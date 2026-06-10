from __future__ import annotations
from pydantic import BaseModel
from typing import Union, Literal


class QueryStatus(BaseModel):
    """Return current roster composition, cost, and solve result summary in one call."""
    type: Literal["query_status"] = "query_status"


# Future queries added here
ModelQuery = Union[QueryStatus]


class RetrievalResult(BaseModel):
    """Returned by every retrieval handler. Read-only equivalent of CommandResult."""
    success: bool
    message: str
    data: dict | None = None

    @classmethod
    def ok(cls, message: str, data: dict | None = None) -> "RetrievalResult":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str) -> "RetrievalResult":
        return cls(success=False, message=message)
