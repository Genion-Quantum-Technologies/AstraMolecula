from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PeptideTaskParams(BaseModel):
    """
    Peptide优化任务参数表模型
    用于存储每个peptide优化任务的详细参数和计算量预测
    """
    id: str                          # 主键，与task表的id关联
    task_id: str                     # 关联的任务ID
    
    # 多肽序列参数
    peptide_sequence: str            # 输入的多肽序列（氨基酸序列）
    peptide_length: int              # 多肽序列长度 = len(peptide_sequence)
    
    # 受体蛋白参数
    receptor_pdb_filename: str       # 受体蛋白PDB文件名
    
    # 优化参数
    n_iterations: int                # 优化迭代总次数
    n_rosetta_runs: int              # 每次迭代中Rosetta的运行次数
    
    # ProteinMPNN参数
    num_seq_per_target: int          # ProteinMPNN每个目标生成的序列数
    proteinmpnn_seed: int            # ProteinMPNN随机数种子
    
    # 计算量评估结果
    total_calculations: int          # 总计算次数 = n_iterations * n_rosetta_runs
    complexity_factor: float         # 复杂度因子 = (peptide_length / 10) ** 1.5
    total_compute_units: float       # 总计算单元 = total_calculations * complexity_factor
    
    # 时间戳
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
