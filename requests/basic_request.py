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

# ============================================
# 2. 为 peptide optimization 定义 Pydantic 模型
# ============================================
class PeptideOptimizationRequest(BaseModel):
    # 肽段序列（FASTA格式的序列部分，不包含>header）
    peptide_sequence: str
    
    # 受体蛋白PDB文件名（用户上传的文件名）
    receptor_pdb_filename: str
    
    # 可选参数
    cores: int = 12  # CPU核心数
    cleanup: bool = True  # 是否清理中间文件
    step: Optional[int] = None  # 运行特定步骤(1-8)，None表示运行完整流程
    
    # ProteinMPNN相关参数
    proteinmpnn_enabled: bool = True  # 是否启用ProteinMPNN优化
    
    # Docking相关参数
    n_poses: int = 10  # adcp命令中的-N参数，生成对接构象数量
    
    # ProteinMPNN序列生成参数
    num_seq_per_target: int = 10  # 每个目标生成的序列数
    proteinmpnn_seed: int = 37  # ProteinMPNN随机数种子
