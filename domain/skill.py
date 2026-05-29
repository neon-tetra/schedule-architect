from pydantic import BaseModel


class Skill(BaseModel):
    """A named skill that agents can hold and call environments can require."""

    id: str
    name: str