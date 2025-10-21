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
        # 使用None，让数据库的DEFAULT CURRENT_TIMESTAMP处理时间
        task = Task(
            id=task_id,
            user_id=user_id,
            task_type=task_type,
            job_dir=job_dir,
            status=TaskStatus.PENDING,
            created_at=None,  # 将由数据库DEFAULT CURRENT_TIMESTAMP设置
            updated_at=None   # 将由数据库DEFAULT CURRENT_TIMESTAMP设置
        )
        TaskRepository.create(task)
        logger.debug("Task created successfully: %s", task_id)
        return task_id

    @staticmethod
    def update_task_status(task_id: str, status: str, 
                          progress_info: Optional[str] = None) -> None:
        """更新任务状态，自动处理时间戳"""
        logger.info("Updating task %s: status=%s", task_id, status)
        
        update_data: Dict[str, Any] = {"status": status}
        
        # 根据状态自动设置时间戳 - 使用数据库NOW()保证时区一致
        if status == "running":
            current_task = TaskService.get_task(task_id)
            if current_task and not current_task.started_at:
                # 使用特殊标记，让update_task方法使用NOW()
                update_data["started_at"] = "NOW()"
        elif status in ["finished", "failed", "cancelled"]:
            # 使用特殊标记，让update_task方法使用NOW()
            update_data["finished_at"] = "NOW()"
            
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
    def get_tasks_with_cost_info(user_id: str, page: int = 1, page_size: int = 20, 
                                task_type: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """
        获取用户任务列表，包含成本信息，支持分页和过滤
        
        Args:
            user_id: 用户ID
            page: 页码，从1开始
            page_size: 每页大小
            task_type: 任务类型过滤
            status: 状态过滤
            
        Returns:
            包含任务列表和分页信息的字典
        """
        # 获取基础任务列表
        all_tasks = TaskRepository.get_by_user(user_id)
        
        # 过滤任务
        filtered_tasks = []
        for task in all_tasks:
            # 任务类型过滤
            if task_type and task.task_type != task_type:
                continue
            # 状态过滤
            if status and task.status != status:
                continue
            filtered_tasks.append(task)
        
        # 计算分页
        total = len(filtered_tasks)
        total_pages = (total + page_size - 1) // page_size  # 向上取整
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total)
        
        # 获取当前页数据
        page_tasks = filtered_tasks[start_idx:end_idx]
        
        # 构建带成本信息的任务列表
        result_tasks = []
        for task in page_tasks:
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
                elif task.task_type in ["peptide_optimization", "generate"]:
                    peptide_params = PeptideTaskParamsRepository.get_by_task_id(task.id)
                    if peptide_params:
                        task_dict["total_compute_units"] = peptide_params.total_compute_units
            except Exception as e:
                logger.warning("Failed to get cost info for task %s: %s", task.id, e)
            
            result_tasks.append(task_dict)
        
        return {
            "tasks": result_tasks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    @staticmethod
    def get_all_tasks_for_admin(limit: int = 100, user_id: Optional[str] = None, 
                               task_type: Optional[str] = None, status: Optional[str] = None) -> List[Task]:
        """
        管理员专用：获取所有任务列表，支持筛选条件
        """
        logger.info("Admin requesting all tasks with filters: user_id=%s, type=%s, status=%s, limit=%d", 
                   user_id, task_type, status, limit)
        return TaskRepository.get_all_tasks_with_filters(
            limit=limit, 
            user_id=user_id, 
            task_type=task_type, 
            status=status
        )