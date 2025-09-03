from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class DockingTaskParams(BaseModel):
    """
    Docking任务参数表模型
    用于存储每个docking任务的详细参数和计算量预测
    """
    id: str                          # 主键，与task表的id关联
    task_id: str                     # 关联的任务ID
    
    # 分子数量参数
    n_ligands: int                   # 用户提交的配体分子数量
    
    # pH参数
    min_ph: float                    # 最小pH值
    max_ph: float                    # 最大pH值
    ph_factor: float = 1.5           # pH因子，固定为1.5（代表平均每个SMILES生成1.5个变体）
    
    # 对接盒子参数
    center_x: float                  # 对接中心X坐标
    center_y: float                  # 对接中心Y坐标
    center_z: float                  # 对接中心Z坐标
    box_size_x: float                # 盒子X尺寸
    box_size_y: float                # 盒子Y尺寸
    box_size_z: float                # 盒子Z尺寸
    box_volume: float                # 盒子体积 = box_size_x * box_size_y * box_size_z
    
    # 对接参数
    exhaustiveness: int              # 搜索彻底性参数
    n_poses: int                     # 生成姿态数量
    n_jobs: int                      # 并行作业数
    
    # 计算量评估结果
    total_molecules: float           # 待处理分子总数 = n_ligands * ph_factor
    core_docking_factor: float       # 核心对接因子 = (exhaustiveness/8)² * (box_volume/8000)
    pose_generation_factor: float    # 姿态生成因子 = 0.05 * (n_poses/10)
    total_compute_units: float       # 总计算单元 = total_molecules * (core_docking_factor + pose_generation_factor)
    
    # 时间戳
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
