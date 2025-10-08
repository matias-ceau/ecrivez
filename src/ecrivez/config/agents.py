from pydantic import BaseModel


class DefaultAgents(BaseModel):
    """Placeholder until real agent schema is designed."""

    default: str = "agent.json"