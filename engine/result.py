from pydantic import BaseModel


class CommandResult(BaseModel):
    """Returned by every handler method and surfaced back to the caller."""

    success: bool
    message: str
    data: dict | None = None

    @classmethod
    def ok(cls, message: str, data: dict | None = None) -> "CommandResult":
        return cls(success=True, message=message, data=data)

    @classmethod
    def fail(cls, message: str) -> "CommandResult":
        return cls(success=False, message=message)