from datetime import datetime
from dataclasses import dataclass


@dataclass
class SubTask:
    id: int
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    completed: bool = False
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

@dataclass
class Task:
    id: int
    title: str
    description: str
    subtasks: list[SubTask]
    created_at: datetime = None
    completed: bool = False
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


    @property
    def completion_percentage(self):
        if not self.subtasks:
            return 0
        completed_count = sum(1 for subtask in self.subtasks if subtask.completed)
        return (completed_count / len(self.subtasks)) * 100
    
    @property
    def total_duration_hours(self):
        total_seconds = sum((subtask.end_time - subtask.start_time).total_seconds() for subtask in self.subtasks)

        return total_seconds / 3600