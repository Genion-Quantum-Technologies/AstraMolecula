from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class TaskStatus:
    """任务状态常量"""
    PENDING = "pending"          # 等待处理
    QUEUED = "queued"           # 已排队
    RUNNING = "running"         # 正在运行
    PROCESSING = "processing"   # 处理中（可包含进度）
    FINISHED = "finished"       # 已完成
    FAILED = "failed"          # 失败
    CANCELLED = "cancelled"    # 已取消
    PAUSED = "paused"          # 暂停


class Task(BaseModel):
    id: str
    user_id: str
    task_type: str  # 'generate' or 'docking'
    job_dir: str
    status: str = TaskStatus.PENDING
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None