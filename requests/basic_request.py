from typing import List, Optional
from pydantic import BaseModel, EmailStr

class UserCreateRequest(BaseModel):
    username: str
    password: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class UserLoginRequest(BaseModel):
    username: str
    password: str

class GenerateRequest(BaseModel):
    constSmiles: str
    varSmiles: str
    mainCls: str
    minorCls: str
    deltaValue: str
    num: int

class GenerateRequestList(BaseModel):
    generateRequestList: List[GenerateRequest]

# ============================================
# 1. 为 docking 定义 Pydantic 模型
# ============================================
class DockingLigand(BaseModel):
    smiles: str
    title: str

class DockingRequest(BaseModel):
    ligands: List[DockingLigand]
    min_ph: float = 6.0
    max_ph: float = 8.0
    n_jobs: int = 8
    
    # 中心坐标参数 (必填)
    center_x: float
    center_y: float
    center_z: float
    
    # 盒子大小参数 (必填，必须提供xyz三个维度)
    box_size_x: float
    box_size_y: float
    box_size_z: float
    
    # 其他参数 (必填)
    exhaustiveness: int = 4
    n_poses: int = 20
