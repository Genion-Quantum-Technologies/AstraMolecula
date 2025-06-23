import uuid
from datetime import datetime
from typing import List

from database.models.task import Task
from database.repositorys.task_repository import TaskRepository

class TaskService:
    @staticmethod
    def create_task(user_id: str, task_type: str, job_dir: str) -> str:
        task_id = uuid.uuid4().hex
        task = Task(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            job_dir=job_dir,
            status='pending',
            created_at=datetime.utcnow(),
            finished_at=None
        )
        TaskRepository.create(task)
        return task_id

    @staticmethod
    def finish_task(task_id: str, status: str = 'finished') -> None:
        TaskRepository.update_status(task_id, status, datetime.utcnow())

    @staticmethod
    def fetch_pending(limit: int = 10) -> List[Task]:
        return TaskRepository.get_pending(limit)