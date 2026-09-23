from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Game(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    target_wins: int
    current_wins: int = 0
    position: int = Field(default=0, index=True)
    mode: str = Field(default="total")  # "total" = Gesamt-Siege, "streak" = Siege am Stück
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def completed(self) -> bool:
        return self.current_wins >= self.target_wins

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "target_wins": self.target_wins,
            "current_wins": self.current_wins,
            "mode": self.mode,
            "completed": self.completed,
        }
