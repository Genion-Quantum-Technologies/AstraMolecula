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
    created_at: Optional[datetime] = None  # 允许为None，由数据库DEFAULT设置
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # ADR 0012 P2 —— 这两列由 compute-foundry operator / Argo 的 onExit 钩子维护。
    #
    # `progress`: 之前 `GET /tasks/{id}/status` 里返回的 progress 是 `getattr(task,'progress',0)`，
    #   而 Task 模型压根没有这个属性、tasks 表也没有这一列 —— 所以它**恒为字面量 0**。
    #   现在列有了、值是真的，把字段补上，那个 getattr 就自动开始说真话。响应体形状不变。
    # `info`: 失败原因。以前 worker 写进 tasks.info，但**没有任何 SELECT 读它**，
    #   于是"任务为什么失败"这件事对外完全不可见。现在 onExit 钩子写入失败步骤的原文。
    progress: int = 0
    info: Optional[str] = None