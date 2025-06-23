from typing import List, Optional
from database.db import get_connection
from database.models.task import Task

class TaskRepository:
    @staticmethod
    def create(task: Task) -> None:
        sql = """
        INSERT INTO tasks (id, user_id, task_type, job_dir, status, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (task.id, task.user_id, task.task_type, task.job_dir, task.status, task.created_at))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update_status(task_id: str, status: str, finished_at: Optional[str] = None) -> None:
        sql = "UPDATE tasks SET status = %s, finished_at = %s WHERE id = %s"
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (status, finished_at, task_id))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_pending(limit: int = 10) -> List[Task]:
        sql = """
        SELECT id, user_id, task_type, job_dir, status, created_at, finished_at
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