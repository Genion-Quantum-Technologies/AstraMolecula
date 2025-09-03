"""
Peptide任务参数服务类
业务逻辑层，处理peptide任务参数的创建、查询等操作
"""
import logging
from typing import Dict, Any, Optional

from database.models.peptide_task_params import PeptideTaskParams
from database.repositorys.peptide_task_params_repository import PeptideTaskParamsRepository
from utils.peptide_cost_calculator import PeptideCostCalculator

logger = logging.getLogger("peptide_task_params_service")


class PeptideTaskParamsService:
    """Peptide任务参数服务类"""
    
    @staticmethod
    def create_task_params(
        task_id: str,
        peptide_sequence: str,
        n_iterations: int,
        n_rosetta_runs: int
    ) -> PeptideTaskParams:
        """
        创建peptide任务参数
        
        Args:
            task_id: 任务ID
            peptide_sequence: 多肽序列
            n_iterations: 迭代次数
            n_rosetta_runs: 每次迭代的Rosetta运行次数
            
        Returns:
            创建的PeptideTaskParams对象
        """
        
        logger.info("Creating peptide task params for task %s", task_id)
        
        try:
            # 使用成本计算器创建参数
            params = PeptideCostCalculator.create_peptide_task_params(
                task_id=task_id,
                peptide_sequence=peptide_sequence,
                n_iterations=n_iterations,
                n_rosetta_runs=n_rosetta_runs
            )
            
            logger.info("Successfully created peptide task params: %.2f CUs", 
                       params.total_compute_units)
            return params
            
        except Exception as e:
            logger.error("Failed to create peptide task params for task %s: %s", task_id, e)
            raise
    
    @staticmethod
    def get_cost_summary(task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务的成本摘要
        
        Args:
            task_id: 任务ID
            
        Returns:
            成本摘要字典，如果任务不存在则返回None
        """
        
        try:
            # 从数据库获取参数
            params = PeptideTaskParamsRepository.get_by_task_id(task_id)
            
            if not params:
                logger.warning("Peptide task params not found for task %s", task_id)
                return None
            
            # 生成成本摘要
            cost_summary = PeptideCostCalculator.get_cost_estimate_summary(params)
            
            # 生成时间预估
            time_estimate = PeptideCostCalculator.estimate_execution_time(params)
            
            return {
                "task_id": task_id,
                "is_preview": False,
                **cost_summary,
                "time_estimate": time_estimate
            }
            
        except Exception as e:
            logger.error("Failed to get cost summary for task %s: %s", task_id, e)
            return None
    
    @staticmethod
    def estimate_cost_before_submission(
        peptide_sequence: str,
        n_iterations: int,
        n_rosetta_runs: int
    ) -> Dict[str, Any]:
        """
        在提交任务前进行成本预估
        
        Args:
            peptide_sequence: 多肽序列
            n_iterations: 迭代次数
            n_rosetta_runs: 每次迭代的Rosetta运行次数
            
        Returns:
            成本预估结果
        """
        
        logger.info("Estimating peptide optimization cost: %d residues, %d iterations, %d runs per iteration", 
                   len(peptide_sequence), n_iterations, n_rosetta_runs)
        
        try:
            return PeptideCostCalculator.estimate_cost_before_submission(
                peptide_sequence=peptide_sequence,
                n_iterations=n_iterations,
                n_rosetta_runs=n_rosetta_runs
            )
        except Exception as e:
            logger.error("Failed to estimate peptide cost: %s", e)
            raise
    
    @staticmethod
    def delete_task_params(task_id: str) -> bool:
        """
        删除任务参数
        
        Args:
            task_id: 任务ID
            
        Returns:
            删除是否成功
        """
        
        try:
            PeptideTaskParamsRepository.delete_by_task_id(task_id)
            logger.info("Deleted peptide task params for task %s", task_id)
            return True
        except Exception as e:
            logger.error("Failed to delete peptide task params for task %s: %s", task_id, e)
            return False
    
    @staticmethod
    def get_task_params(task_id: str) -> Optional[PeptideTaskParams]:
        """
        获取任务参数
        
        Args:
            task_id: 任务ID
            
        Returns:
            PeptideTaskParams对象，如果不存在则返回None
        """
        
        try:
            return PeptideTaskParamsRepository.get_by_task_id(task_id)
        except Exception as e:
            logger.error("Failed to get peptide task params for task %s: %s", task_id, e)
            return None
    
    @staticmethod
    def get_simple_cost_info(task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取简化的成本信息（用于任务提交响应）
        
        Args:
            task_id: 任务ID
            
        Returns:
            简化的成本信息
        """
        
        try:
            params = PeptideTaskParamsRepository.get_by_task_id(task_id)
            
            if not params:
                return None
            
            # 计算复杂度分类
            cu = params.total_compute_units
            if cu < 1:
                complexity_category = "Low"
            elif cu < 10:
                complexity_category = "Medium"
            elif cu < 100:
                complexity_category = "High"
            elif cu < 1000:
                complexity_category = "Very High"
            else:
                complexity_category = "Extreme"
            
            per_iteration_cost = params.total_compute_units / params.n_iterations
            
            return {
                "total_compute_units": round(params.total_compute_units, 2),
                "per_iteration_cost": round(per_iteration_cost, 3),
                "complexity_category": complexity_category,
                "peptide_length": params.peptide_length,
                "total_rosetta_runs": params.total_calculations
            }
            
        except Exception as e:
            logger.error("Failed to get simple cost info for task %s: %s", task_id, e)
            return None
