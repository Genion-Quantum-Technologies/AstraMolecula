from typing import List, Optional, Dict, Any
import json
from astra_molecula.db.db import get_connection
from astra_molecula.db.models.task import Task

class TaskRepository:
    @staticmethod
    def create(task: Task) -> None:
        # 如果created_at为None，则让数据库使用DEFAULT CURRENT_TIMESTAMP
        # updated_at 字段不在INSERT中指定，让数据库使用DEFAULT CURRENT_TIMESTAMP
        if task.created_at is None:
            sql = """
            INSERT INTO tasks (
                id, user_id, task_type, job_dir, status, started_at, finished_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                task.id, task.user_id, task.task_type, task.job_dir, 
                task.status, task.started_at, task.finished_at
            )
        else:
            sql = """
            INSERT INTO tasks (
                id, user_id, task_type, job_dir, status, created_at, started_at, finished_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (
                task.id, task.user_id, task.task_type, task.job_dir, 
                task.status, task.created_at, task.started_at, task.finished_at
            )
        
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, values)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update_task(task_id: str, update_data: Dict[str, Any]) -> None:
        """通用的任务更新方法"""
        if not update_data:
            return
            
        # 构建SQL语句
        set_clauses = []
        values = []
        
        for key, value in update_data.items():
            if key == "metadata" and value is not None:
                set_clauses.append(f"{key} = %s")
                values.append(json.dumps(value))
            elif value == "NOW()":  # 特殊处理NOW()函数
                set_clauses.append(f"{key} = CURRENT_TIMESTAMP")
                # 不添加到values中，因为CURRENT_TIMESTAMP直接在SQL中
            else:
                set_clauses.append(f"{key} = %s")
                values.append(value)
        
        values.append(task_id)
        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = %s"
        
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, values)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update_status(task_id: str, status: str, finished_at: Optional[str] = None) -> None:
        """保持向后兼容的状态更新方法"""
        update_data = {"status": status}
        if finished_at:
            update_data["finished_at"] = finished_at
        TaskRepository.update_task(task_id, update_data)

    @staticmethod
    def get_pending(limit: int = 10) -> List[Task]:
        sql = """
        SELECT id, user_id, task_type, job_dir, status, progress, info, created_at, started_at, finished_at, updated_at
          FROM tasks
         WHERE status = 'pending'
      ORDER BY created_at ASC
         LIMIT %s
        """
        conn = get_connection()
        tasks: List[Task] = []
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (limit,))
                for row in cur.fetchall():
                    tasks.append(Task(**row))
        finally:
            conn.close()
        return tasks

    @staticmethod
    def get(task_id: str) -> Optional[Task]:
        sql = """
        SELECT id, user_id, task_type, job_dir, status, progress, info, created_at, started_at, finished_at, updated_at
          FROM tasks
         WHERE id = %s
        """
        conn = get_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (task_id,))
                row = cur.fetchone()
                if row:
                    return Task(**row)
        finally:
            conn.close()
        return None

    @staticmethod
    def get_by_user(user_id: str) -> List[Task]:
        """
        按 user_id 查询该用户提交的所有任务，按创建时间倒序返回。
        """
        sql = """
        SELECT id, user_id, task_type, job_dir, status, progress, info, created_at, started_at, finished_at, updated_at
          FROM tasks
         WHERE user_id = %s
      ORDER BY created_at DESC
        """
        conn = get_connection()
        tasks: List[Task] = []
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (user_id,))
                for row in cur.fetchall():
                    tasks.append(Task(**row))
        finally:
            conn.close()
        return tasks

    @staticmethod
    def get_all_tasks_with_filters(limit: int = 100, user_id: Optional[str] = None, 
                                 task_type: Optional[str] = None, status: Optional[str] = None) -> List[Task]:
        """
        管理员专用：获取所有任务列表，支持筛选条件
        """
        where_clauses = []
        values = []
        
        if user_id:
            where_clauses.append("user_id = %s")
            values.append(user_id)
        
        if task_type:
            where_clauses.append("task_type = %s")
            values.append(task_type)
        
        if status:
            where_clauses.append("status = %s")
            values.append(status)
        
        where_clause = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        sql = f"""
        SELECT id, user_id, task_type, job_dir, status, progress, info, created_at, started_at, finished_at, updated_at
          FROM tasks
         {where_clause}
      ORDER BY created_at DESC
         LIMIT %s
        """
        
        values.append(limit)
        
        conn = get_connection()
        tasks: List[Task] = []
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, values)
                for row in cur.fetchall():
                    tasks.append(Task(**row))
        finally:
            conn.close()
        return tasks
