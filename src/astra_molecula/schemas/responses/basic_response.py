from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class Fragment(BaseModel):
    variable_smiles: str
    constant_smiles: str
    record_id: str
    normalized_smiles: str
    attachment_order: int

class FragmentResponse(BaseModel):
    fragments: List[Fragment]


class MoleculeResponse(BaseModel):
    smile: str
    molwt: float
    tpsa: float
    slogp: float
    sa: float
    qed: float

class DockResponse(BaseModel):
    title: str
    pose: int
    score: float
    smiles: str
    file: str
    protein_path: Optional[str] = None  # 添加protein路径字段
    share_url: Optional[str] = None  # 公开分享链接
    
    # 扩展字段，提供更多信息
    ligand_properties: Optional[dict] = None  # 配体属性（分子量、TPSA等）
    docking_parameters: Optional[dict] = None  # 对接参数
    file_size: Optional[int] = None  # SDF文件大小
    creation_time: Optional[datetime] = None  # 文件创建时间
    
class DockingTaskResponse(BaseModel):
    """对接任务详细响应"""
    task_id: str
    status: str
    message: str
    details: dict
    next_steps: dict
    
class DockingErrorResponse(BaseModel):
    """对接任务错误响应"""
    error: str
    message: str
    details: dict

class TaskResponse(BaseModel):
    id: str
    user_id: str
    task_type: str
    job_dir: str
    status: str
    created_at: datetime
    finished_at: Optional[datetime]
    total_compute_units: Optional[float] = None  # 添加计算成本字段

class PaginatedTasksResponse(BaseModel):
    """分页任务列表响应"""
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int
    total_pages: int