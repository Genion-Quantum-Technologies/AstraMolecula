from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Task:
    id: str
    user_id: str
    task_type: str
    job_dir: str
    status: str
    created_at: datetime
    finished_at: Optional[datetime]