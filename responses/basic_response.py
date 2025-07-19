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

class TaskResponse(BaseModel):
    id: str
    user_id: str
    task_type: str
    job_dir: str
    status: str
    created_at: datetime
    finished_at: Optional[datetime]