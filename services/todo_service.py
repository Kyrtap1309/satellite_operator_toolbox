import json
import logging
import os
from datetime import datetime
from typing import Any

from models.todo import SubTask, Task

logger = logging.getLogger(__name__)


class TodoService:
    def __init__(self, data_file: str = "data/todos.json"):
        self.data_file = data_file
        self.tasks: list[Task] = []
        self._ensure_data_dir()
        self.load_tasks()

    def _ensure_data_dir(self) -> None:
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)

    def load_tasks(self) -> None:
        """Load tasks from JSON file"""
        try:
            logger.info(f"Attempting to load tasks from: {os.path.abspath(self.data_file)}")
            logger.info(f"File exists: {os.path.exists(self.data_file)}")

            if os.path.exists(self.data_file):
                with open(self.data_file, encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded JSON data: {len(data)} tasks found")

                    self.tasks = []
                    for task_data in data:
                        logger.info(f"Processing task: {task_data.get('title', 'Unknown')}")
                        subtasks = []
                        for subtask_data in task_data.get("subtasks", []):
                            start_time = None
                            end_time = None
                            if subtask_data.get("start_time"):
                                start_time = datetime.fromisoformat(subtask_data["start_time"])
                            if subtask_data.get("end_time"):
                                end_time = datetime.fromisoformat(subtask_data["end_time"])

                            subtask = SubTask(
                                id=subtask_data["id"],
                                title=subtask_data["title"],
                                description=subtask_data["description"],
                                start_time=start_time,
                                end_time=end_time,
                                completed=subtask_data.get("completed", False),
                                created_at=datetime.fromisoformat(subtask_data.get("created_at", datetime.now().isoformat())),
                            )
                            subtasks.append(subtask)

                        task = Task(
                            id=task_data["id"],
                            title=task_data["title"],
                            description=task_data["description"],
                            subtasks=subtasks,
                            completed=task_data.get("completed", False),
                            created_at=datetime.fromisoformat(task_data.get("created_at", datetime.now().isoformat())),
                        )
                        self.tasks.append(task)

                    logger.info(f"Successfully loaded {len(self.tasks)} tasks")
            else:
                logger.warning(f"Tasks file does not exist: {self.data_file}")
                self.tasks = []
        except Exception as e:
            logger.error(f"Error loading tasks: {e}")
            self.tasks = []

    def save_tasks(self) -> None:
        """Save tasks to JSON file"""
        try:
            logger.info(f"Saving {len(self.tasks)} tasks to: {os.path.abspath(self.data_file)}")
            data = []
            for task in self.tasks:
                subtasks_data = [
                    {
                        "id": subtask.id,
                        "title": subtask.title,
                        "description": subtask.description,
                        "start_time": subtask.start_time.isoformat() if subtask.start_time else None,
                        "end_time": subtask.end_time.isoformat() if subtask.end_time else None,
                        "completed": subtask.completed,
                        "created_at": subtask.created_at.isoformat() if subtask.created_at else datetime.now().isoformat(),
                    }
                    for subtask in task.subtasks
                ]

                data.append(
                    {
                        "id": task.id,
                        "title": task.title,
                        "description": task.description,
                        "subtasks": subtasks_data,
                        "completed": task.completed,
                        "created_at": task.created_at.isoformat() if task.created_at else datetime.now().isoformat(),
                    }
                )

            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Successfully saved tasks to: {os.path.abspath(self.data_file)}")
        except Exception as e:
            logger.error(f"Error saving tasks: {e}")

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks"""
        return self.tasks

    def get_task_by_id(self, task_id: int) -> Task | None:
        """Get task by ID"""
        return next((task for task in self.tasks if task.id == task_id), None)

    def create_task(self, title: str, description: str) -> Task:
        """Create new task"""
        new_id = max([task.id for task in self.tasks], default=0) + 1
        task = Task(id=new_id, title=title, description=description, subtasks=[])
        self.tasks.append(task)
        self.save_tasks()
        return task

    def add_subtask(self, task_id: int, title: str, description: str, start_time: datetime | None, end_time: datetime | None) -> bool:
        """Add subtask to existing task"""
        task = self.get_task_by_id(task_id)
        if not task:
            return False

        max_id = 0
        for existing_task in self.tasks:
            for subtask in existing_task.subtasks:
                max_id = max(max_id, subtask.id)

        subtask = SubTask(id=max_id + 1, title=title, description=description, start_time=start_time, end_time=end_time)

        task.subtasks.append(subtask)
        self.save_tasks()
        return True

    def toggle_subtask_completion(self, task_id: int, subtask_id: int) -> bool:
        """Toggle subtask completion status"""
        task = self.get_task_by_id(task_id)
        if not task:
            return False

        subtask = next((st for st in task.subtasks if st.id == subtask_id), None)
        if not subtask:
            return False

        subtask.completed = not subtask.completed
        self.save_tasks()
        return True

    def delete_task(self, task_id: int) -> bool:
        """Delete task"""
        task = self.get_task_by_id(task_id)
        if not task:
            return False

        self.tasks.remove(task)
        self.save_tasks()
        return True

    def delete_subtask(self, task_id: int, subtask_id: int) -> bool:
        """Delete subtask"""
        task = self.get_task_by_id(task_id)
        if not task:
            return False

        subtask = next((st for st in task.subtasks if st.id == subtask_id), None)
        if not subtask:
            return False

        task.subtasks.remove(subtask)
        self.save_tasks()
        return True

    def get_timeline_data(self, task_id: int | None = None) -> list[dict[str, Any]]:
        """Get timeline data for visualization"""
        timeline_data = []
        tasks_to_process = [self.get_task_by_id(task_id)] if task_id else self.tasks

        for task in tasks_to_process:
            if not task:
                continue

            # Use list.extend with list comprehension for better performance
            timeline_data.extend(
                [
                    {
                        "id": f"task_{task.id}_subtask_{subtask.id}",
                        "content": f"{subtask.title}",
                        "start": subtask.start_time.isoformat() + "Z",  # Add Z to indicate UTC
                        "end": subtask.end_time.isoformat() + "Z",  # Add Z to indicate UTC
                        "group": f"task_{task.id}",
                        "className": "completed" if subtask.completed else "pending",
                        "title": f"{task.title} - {subtask.title}\n{subtask.description}",
                    }
                    for subtask in task.subtasks
                    if subtask.start_time is not None and subtask.end_time is not None
                ]
            )

        return timeline_data

    def get_timeline_groups(self, task_id: int | None = None) -> list[dict[str, Any]]:
        """Get timeline groups for visualization"""
        groups = []
        tasks_to_process = [self.get_task_by_id(task_id)] if task_id else self.tasks

        for task in tasks_to_process:
            if not task:
                continue

            groups.append({"id": f"task_{task.id}", "content": f"{task.title} ({task.completion_percentage:.0f}%)"})

        return groups

    def edit_subtask(
        self, task_id: int, subtask_id: int, title: str, description: str, start_time: datetime | None, end_time: datetime | None
    ) -> bool:
        """Edit existing subtask"""
        task = self.get_task_by_id(task_id)
        if not task:
            return False

        subtask = next((st for st in task.subtasks if st.id == subtask_id), None)
        if not subtask:
            return False

        subtask.title = title
        subtask.description = description
        subtask.start_time = start_time
        subtask.end_time = end_time

        self.save_tasks()
        return True
