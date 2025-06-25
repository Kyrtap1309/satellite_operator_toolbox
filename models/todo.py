from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SubTask:
    id: int
    title: str
    description: str
    start_time: datetime | None
    end_time: datetime | None
    completed: bool = False
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Task:
    id: int
    title: str
    description: str
    subtasks: list[SubTask] = field(default_factory=list)
    created_at: datetime | None = None
    completed: bool = False
    sort_order: int = 0

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now()

    @property
    def completion_percentage(self) -> float:
        if not self.subtasks:
            return 0
        completed_count = sum(1 for subtask in self.subtasks if subtask.completed)
        return (completed_count / len(self.subtasks)) * 100

    @property
    def total_duration_hours(self) -> float:
        total_seconds = sum(
            (subtask.end_time - subtask.start_time).total_seconds() for subtask in self.subtasks if subtask.start_time and subtask.end_time
        )

        return total_seconds / 3600
