import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from database.models.task import Task, TaskStatus
from database.repositorys.task_repository import TaskRepository

logger = logging.getLogger("database.task_service")

class TaskService:
    @staticmethod
    def create_task(user_id: str, task_type: str, job_dir: str, 
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        task_id = uuid.uuid4().hex
        logger.info("Creating new task: id=%s, user_id=%s, type=%s", 
                   task_id, user_id, task_type)
        task = Task(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            job_dir=job_dir,
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
        )
        TaskRepository.create(task)
        logger.debug("Task created successfully: %s", task_id)
        return task_id

    @staticmethod
    def update_task_status(task_id: str, status: str, 
                          progress_info: Optional[str] = None) -> None:
        """更新任务状态，自动处理时间戳"""
        logger.info("Updating task %s: status=%s", task_id, status)
        
        update_data = {"status": status}
        
        # 根据状态自动设置时间戳
        if status == "running" and not TaskService.get_task(task_id).started_at:
            update_data["started_at"] = datetime.utcnow()
        elif status in ["finished", "failed", "cancelled"]:
            update_data["finished_at"] = datetime.utcnow()
            
        TaskRepository.update_task(task_id, update_data)

    @staticmethod
    def finish_task(task_id: str, status: str = TaskStatus.FINISHED) -> None:
        """完成任务（保持向后兼容）"""
        TaskService.update_task_status(task_id, status)

    @staticmethod
    def fetch_pending(limit: int = 10) -> List[Task]:
        return TaskRepository.get_pending(limit)

    @staticmethod
    def get_task(task_id: str) -> Optional[Task]:
        return TaskRepository.get(task_id)

    @staticmethod
    def get_tasks_by_user(user_id: str) -> List[Task]:
        """
        返回指定用户的所有任务（按创建时间倒序，可根据需要调整排序或分页）。
        """
        return TaskRepository.get_by_user(user_id)