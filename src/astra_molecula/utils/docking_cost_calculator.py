"""
成本计算模块
基于理论计算总量模型计算分子对接任务的计算成本
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any

from astra_molecula.db.models.docking_task_params import DockingTaskParams
from astra_molecula.db.repositories.docking_task_params_repository import DockingTaskParamsRepository

logger = logging.getLogger("cost_calculator")


class CostCalculator:
    """
    理论计算总量评估器
    提供不依赖硬件的、纯理论的计算复杂度评分
    """
    
    # 标准参数定义
    STANDARD_EXHAUSTIVENESS = 8
    STANDARD_BOX_VOLUME = 8000  # 20 x 20 x 20
    STANDARD_N_POSES = 10
    PH_FACTOR = 1.5  # 平均每个SMILES生成1.5个变体
    POSE_WEIGHT = 0.05  # 姿态生成开销权重（占总计算量的5%）
    
    @staticmethod
    def calculate_cost_factors(
        n_ligands: int,
        min_ph: float,
        max_ph: float,
        center_x: float,
        center_y: float,
        center_z: float,
        box_size_x: float,
        box_size_y: float,
        box_size_z: float,
        exhaustiveness: int,
        n_poses: int,
        n_jobs: int
    ) -> Dict[str, float]:
        """
        计算所有成本相关因子
        
        Args:
            n_ligands: 配体分子数量
            min_ph: 最小pH值
            max_ph: 最大pH值
            center_x/y/z: 对接中心坐标
            box_size_x/y/z: 对接盒子尺寸
            exhaustiveness: 搜索彻底性
            n_poses: 生成姿态数
            n_jobs: 并行作业数
            
        Returns:
            包含所有计算因子的字典
        """
        
        # 1. 计算基础参数
        box_volume = box_size_x * box_size_y * box_size_z
        total_molecules = n_ligands * CostCalculator.PH_FACTOR
        
        # 2. 计算核心对接因子
        # F_core = (exhaustiveness / 8)² × (box_volume / 8000)
        exhaustiveness_factor = (exhaustiveness / CostCalculator.STANDARD_EXHAUSTIVENESS) ** 2
        volume_factor = box_volume / CostCalculator.STANDARD_BOX_VOLUME
        core_docking_factor = exhaustiveness_factor * volume_factor
        
        # 3. 计算姿态生成因子
        # F_pose = 0.05 × (n_poses / 10)
        pose_generation_factor = CostCalculator.POSE_WEIGHT * (n_poses / CostCalculator.STANDARD_N_POSES)
        
        # 4. 计算总计算单元
        # Total CUs = total_molecules × [core_docking_factor + pose_generation_factor]
        per_molecule_cost = core_docking_factor + pose_generation_factor
        total_compute_units = total_molecules * per_molecule_cost
        
        return {
            "box_volume": box_volume,
            "total_molecules": total_molecules,
            "exhaustiveness_factor": exhaustiveness_factor,
            "volume_factor": volume_factor,
            "core_docking_factor": core_docking_factor,
            "pose_generation_factor": pose_generation_factor,
            "per_molecule_cost": per_molecule_cost,
            "total_compute_units": total_compute_units
        }
    
    @staticmethod
    def create_docking_task_params(
        task_id: str,
        n_ligands: int,
        min_ph: float,
        max_ph: float,
        center_x: float,
        center_y: float,
        center_z: float,
        box_size_x: float,
        box_size_y: float,
        box_size_z: float,
        exhaustiveness: int,
        n_poses: int,
        n_jobs: int
    ) -> DockingTaskParams:
        """
        创建并保存docking任务参数记录
        
        Returns:
            创建的DockingTaskParams对象
        """
        
        # 计算所有成本因子
        cost_factors = CostCalculator.calculate_cost_factors(
            n_ligands=n_ligands,
            min_ph=min_ph,
            max_ph=max_ph,
            center_x=center_x,
            center_y=center_y,
            center_z=center_z,
            box_size_x=box_size_x,
            box_size_y=box_size_y,
            box_size_z=box_size_z,
            exhaustiveness=exhaustiveness,
            n_poses=n_poses,
            n_jobs=n_jobs
        )
        
        # 创建参数对象
        params = DockingTaskParams(
            id=str(uuid.uuid4()),
            task_id=task_id,
            n_ligands=n_ligands,
            min_ph=min_ph,
            max_ph=max_ph,
            ph_factor=CostCalculator.PH_FACTOR,
            center_x=center_x,
            center_y=center_y,
            center_z=center_z,
            box_size_x=box_size_x,
            box_size_y=box_size_y,
            box_size_z=box_size_z,
            box_volume=cost_factors["box_volume"],
            exhaustiveness=exhaustiveness,
            n_poses=n_poses,
            n_jobs=n_jobs,
            total_molecules=cost_factors["total_molecules"],
            core_docking_factor=cost_factors["core_docking_factor"],
            pose_generation_factor=cost_factors["pose_generation_factor"],
            total_compute_units=cost_factors["total_compute_units"],
            created_at=datetime.now()  # 这个值不会被插入数据库，仅用于对象初始化
        )
        
        # 保存到数据库
        try:
            DockingTaskParamsRepository.create(params)
            logger.info("Created docking task params for task %s: %.2f CUs", 
                       task_id, params.total_compute_units)
        except Exception as e:
            logger.error("Failed to save docking task params for task %s: %s", task_id, e)
            raise
        
        return params
    
    @staticmethod
    def get_cost_estimate_summary(params: DockingTaskParams) -> Dict[str, Any]:
        """
        生成成本估算摘要，用于向用户展示
        
        Args:
            params: DockingTaskParams对象
            
        Returns:
            格式化的成本摘要
        """
        
        # 计算相对于标准配置的倍数
        exhaustiveness_multiplier = (params.exhaustiveness / CostCalculator.STANDARD_EXHAUSTIVENESS) ** 2
        volume_multiplier = params.box_volume / CostCalculator.STANDARD_BOX_VOLUME
        poses_multiplier = params.n_poses / CostCalculator.STANDARD_N_POSES
        
        return {
            "task_id": params.task_id,
            "compute_units": {
                "total": round(params.total_compute_units, 2),
                "per_ligand": round(params.total_compute_units / params.n_ligands, 2),
                "baseline": "1 CU = standard config (exhaustiveness=8, box=20x20x20, poses=10)"
            },
            "input_summary": {
                "ligands": params.n_ligands,
                "estimated_molecules": round(params.total_molecules, 1),
                "ph_range": f"{params.min_ph:.1f} - {params.max_ph:.1f}",
                "box_volume": f"{params.box_volume:.0f} Ų",
                "exhaustiveness": params.exhaustiveness,
                "poses": params.n_poses,
                "parallel_jobs": params.n_jobs
            },
            "complexity_factors": {
                "exhaustiveness_impact": f"{exhaustiveness_multiplier:.2f}x",
                "box_volume_impact": f"{volume_multiplier:.2f}x",
                "poses_impact": f"{poses_multiplier:.2f}x"
            },
            "cost_breakdown": {
                "core_docking": round(params.core_docking_factor, 4),
                "pose_generation": round(params.pose_generation_factor, 4),
                "total_per_molecule": round(params.core_docking_factor + params.pose_generation_factor, 4)
            },
            "comparison": {
                "vs_standard_single_ligand": f"{params.total_compute_units:.1f}x",
                "category": CostCalculator._get_cost_category(params.total_compute_units)
            }
        }
    
    @staticmethod
    def _get_cost_category(total_cus: float) -> str:
        """根据计算单元数量分类任务成本"""
        if total_cus < 1:
            return "Low"
        elif total_cus < 10:
            return "Medium"
        elif total_cus < 100:
            return "High"
        elif total_cus < 1000:
            return "Very High"
        else:
            return "Extreme"
    
    @staticmethod
    def estimate_execution_time(total_cus: float, hardware_factor: float = 1.0) -> Dict[str, str]:
        """
        估算执行时间（可选功能）
        
        Args:
            total_cus: 总计算单元
            hardware_factor: 硬件因子（默认1.0为标准硬件）
            
        Returns:
            时间估算
        """
        # 基准：1 CU ≈ 1分钟（在标准硬件上）
        base_minutes = total_cus / hardware_factor
        
        hours = int(base_minutes // 60)
        minutes = int(base_minutes % 60)
        
        if hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"
            
        return {
            "estimated_time": time_str,
            "total_minutes": round(base_minutes, 1),
            "note": "Estimation based on standard hardware (hardware_factor=1.0)"
        }
