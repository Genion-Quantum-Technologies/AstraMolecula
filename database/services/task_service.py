import uuid
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from database.models.task import Task, TaskStatus
from database.repositorys.task_repository import TaskRepository
from database.repositorys.docking_task_params_repository import DockingTaskParamsRepository
from database.repositorys.peptide_task_params_repository import PeptideTaskParamsRepository

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
    
    @staticmethod
    def get_tasks_with_cost_info(user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户任务列表，包含成本信息
        
        Args:
            user_id: 用户ID
            
        Returns:
            包含成本信息的任务列表
        """
        # 获取基础任务列表
        tasks = TaskRepository.get_by_user(user_id)
        
        result = []
        for task in tasks:
            task_dict = {
                "id": task.id,
                "user_id": task.user_id,
                "task_type": task.task_type,
                "job_dir": task.job_dir,
                "status": task.status,
                "created_at": task.created_at,
                "finished_at": task.finished_at,
                "total_compute_units": None
            }
            
            # 根据任务类型获取成本信息
            try:
                if task.task_type == "docking":
                    docking_params = DockingTaskParamsRepository.get_by_task_id(task.id)
                    if docking_params:
                        task_dict["total_compute_units"] = docking_params.total_compute_units
                elif task.task_type == "peptide_optimization":
                    peptide_params = PeptideTaskParamsRepository.get_by_task_id(task.id)
                    if peptide_params:
                        task_dict["total_compute_units"] = peptide_params.total_compute_units
            except Exception as e:
                logger.warning("Failed to get cost info for task %s: %s", task.id, e)
            
            result.append(task_dict)
        
        return result