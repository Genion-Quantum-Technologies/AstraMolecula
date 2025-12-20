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
    receptor_filename: str  # 必填：用户上传的受体PDBQT文件名
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
    
    # 系统固定参数（不再允许用户配置）
    # cores: 固定为12（服务端自动配置）
    # cleanup: 固定为True（自动清理中间文件）
    # step: 固定为None（执行完整优化流程）
    # proteinmpnn_enabled: 固定为True（始终启用ProteinMPNN）
    # n_poses: 固定为10（服务端自动配置）
    
    # ProteinMPNN序列生成参数（用户可配置）
    num_seq_per_target: int = 10  # 每个目标生成的序列数
    proteinmpnn_seed: int = 37  # ProteinMPNN随机数种子
    
    # 成本计算参数（用户可配置）
    n_iterations: int = 5  # 优化迭代次数（默认5次）
    n_rosetta_runs: int = 20  # 每次迭代中Rosetta的运行次数（默认20次）
    
    # 向后兼容性字段（接受但忽略）
    cores: Optional[int] = None  # 废弃字段，将被忽略
    cleanup: Optional[bool] = None  # 废弃字段，将被忽略
    step: Optional[int] = None  # 废弃字段，将被忽略
    proteinmpnn_enabled: Optional[bool] = None  # 废弃字段，将被忽略
    n_poses: Optional[int] = None  # 废弃字段，将被忽略
