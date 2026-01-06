import logging
from typing import Optional, Dict, Any

from database.models.docking_task_params import DockingTaskParams
from database.repositorys.docking_task_params_repository import DockingTaskParamsRepository
from utils.docking_cost_calculator import CostCalculator

logger = logging.getLogger("database.docking_task_params_service")


class DockingTaskParamsService:
    """
    Docking任务参数服务层
    处理任务参数的创建、查询和成本计算
    """
    
    @staticmethod
    def create_task_params(
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
        创建docking任务参数记录
        
        Returns:
            创建的DockingTaskParams对象
        """
        logger.info("Creating docking task params for task %s", task_id)
        
        # 确保表存在
        DockingTaskParamsRepository.create_table_if_not_exists()
        
        # 使用成本计算器创建参数
        params = CostCalculator.create_docking_task_params(
            task_id=task_id,
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
        
        logger.debug("Docking task params created with %.2f total CUs", params.total_compute_units)
        return params
    
    @staticmethod
    def get_task_params(task_id: str) -> Optional[DockingTaskParams]:
        """获取任务参数"""
        return DockingTaskParamsRepository.get_by_task_id(task_id)
    
    @staticmethod
    def get_cost_summary(task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务的成本摘要
        
        Returns:
            格式化的成本摘要，如果任务不存在返回None
        """
        params = DockingTaskParamsRepository.get_by_task_id(task_id)
        if not params:
            logger.warning("No docking task params found for task %s", task_id)
            return None
        
        return CostCalculator.get_cost_estimate_summary(params)
    
    @staticmethod
    def estimate_cost_before_submission(
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
    ) -> Dict[str, Any]:
        """
        在任务提交前预估成本
        不保存到数据库，仅用于用户预览
        
        Returns:
            成本预估结果
        """
        logger.info("Calculating cost estimate for potential docking task")
        
        # 计算成本因子
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
        
        # 创建临时参数对象用于生成摘要
        from datetime import datetime
        import uuid
        
        temp_params = DockingTaskParams(
            id=str(uuid.uuid4()),
            task_id="preview",
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
            created_at=datetime.utcnow()
        )
        
        summary = CostCalculator.get_cost_estimate_summary(temp_params)
        
        # 添加预估时间
        time_estimate = CostCalculator.estimate_execution_time(cost_factors["total_compute_units"])
        summary["time_estimate"] = time_estimate
        
        # 标记为预览
        summary["is_preview"] = True
        summary["task_id"] = "preview"
        
        logger.debug("Cost preview calculated: %.2f CUs", cost_factors["total_compute_units"])
        return summary
    
    @staticmethod
    def delete_task_params(task_id: str) -> bool:
        """删除任务参数"""
        logger.info("Deleting docking task params for task %s", task_id)
        return DockingTaskParamsRepository.delete_by_task_id(task_id)
