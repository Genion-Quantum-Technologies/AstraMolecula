"""
Peptide优化成本计算模块
基于理论计算总量模型计算Peptide优化任务的计算成本
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from database.models.peptide_task_params import PeptideTaskParams
from database.repositorys.peptide_task_params_repository import PeptideTaskParamsRepository

logger = logging.getLogger("peptide_cost_calculator")


class PeptideCostCalculator:
    """
    Peptide优化理论计算总量评估器
    提供不依赖硬件的、纯理论的计算复杂度评分
    """
    
    # 标准参数定义
    STANDARD_PEPTIDE_LENGTH = 10    # 标准多肽长度（氨基酸数量）
    COMPLEXITY_EXPONENT = 1.5       # 复杂度因子的指数（介于线性和二次方之间）
    
    @staticmethod
    def calculate_cost_factors(
        peptide_sequence: str,
        n_iterations: int,
        n_rosetta_runs: int
    ) -> Dict[str, Any]:
        """
        计算所有成本相关因子
        
        Args:
            peptide_sequence: 多肽序列（氨基酸序列）
            n_iterations: 优化迭代总次数
            n_rosetta_runs: 每次迭代中Rosetta的运行次数
            
        Returns:
            包含所有计算因子的字典
        """
        
        # 1. 计算基础参数
        peptide_length = len(peptide_sequence)
        total_calculations = n_iterations * n_rosetta_runs
        
        # 2. 计算复杂度因子
        # F_length = (peptide_length / 10) ** 1.5
        complexity_factor = (peptide_length / PeptideCostCalculator.STANDARD_PEPTIDE_LENGTH) ** PeptideCostCalculator.COMPLEXITY_EXPONENT
        
        # 3. 计算总计算单元
        # Total CUs = (n_iterations × n_rosetta_runs) × (len(peptide_sequence) / 10) ** 1.5
        total_compute_units = total_calculations * complexity_factor
        
        return {
            "peptide_length": peptide_length,
            "total_calculations": total_calculations,
            "complexity_factor": complexity_factor,
            "total_compute_units": total_compute_units,
            # 分解因子用于详细分析
            "length_impact": complexity_factor,
            "iterations_impact": n_iterations,
            "rosetta_runs_impact": n_rosetta_runs
        }
    
    @staticmethod
    def create_peptide_task_params(
        task_id: str,
        peptide_sequence: str,
        receptor_pdb_filename: str,
        n_iterations: int,
        n_rosetta_runs: int,
        num_seq_per_target: int,
        proteinmpnn_seed: int
    ) -> PeptideTaskParams:
        """
        创建并保存peptide任务参数记录
        
        Returns:
            创建的PeptideTaskParams对象
        """
        
        # 计算所有成本因子
        cost_factors = PeptideCostCalculator.calculate_cost_factors(
            peptide_sequence=peptide_sequence,
            n_iterations=n_iterations,
            n_rosetta_runs=n_rosetta_runs
        )
        
        # 创建参数对象
        params = PeptideTaskParams(
            id=uuid.uuid4().hex,
            task_id=task_id,
            peptide_sequence=peptide_sequence,
            peptide_length=cost_factors["peptide_length"],
            receptor_pdb_filename=receptor_pdb_filename,
            n_iterations=n_iterations,
            n_rosetta_runs=n_rosetta_runs,
            num_seq_per_target=num_seq_per_target,
            proteinmpnn_seed=proteinmpnn_seed,
            total_calculations=cost_factors["total_calculations"],
            complexity_factor=cost_factors["complexity_factor"],
            total_compute_units=cost_factors["total_compute_units"],
            created_at=datetime.now()  # 这个值不会被插入数据库，仅用于对象初始化
        )
        
        # 保存到数据库
        try:
            PeptideTaskParamsRepository.create(params)
            logger.info("Created peptide task params for task %s: %.2f CUs", 
                       task_id, params.total_compute_units)
        except Exception as e:
            logger.error("Failed to save peptide task params for task %s: %s", task_id, e)
            raise
        
        return params
    
    @staticmethod
    def get_cost_estimate_summary(params: PeptideTaskParams) -> Dict[str, Any]:
        """
        生成成本估算摘要，用于向用户展示
        
        Args:
            params: PeptideTaskParams对象
            
        Returns:
            格式化的成本估算摘要
        """
        
        # 分类复杂度等级
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
        
        # 计算影响因子的倍数
        length_impact = params.complexity_factor
        per_iteration_cost = params.total_compute_units / params.total_calculations
        
        return {
            "compute_units": {
                "total": round(params.total_compute_units, 6),
                "per_iteration": round(per_iteration_cost, 6),
                "per_rosetta_run": round(per_iteration_cost / params.n_rosetta_runs, 6),
                "baseline": f"1 CU = single Rosetta run on {PeptideCostCalculator.STANDARD_PEPTIDE_LENGTH}-residue peptide"
            },
            "input_summary": {
                "peptide_sequence": params.peptide_sequence,
                "peptide_length": f"{params.peptide_length} residues",
                "total_iterations": params.n_iterations,
                "rosetta_runs_per_iteration": params.n_rosetta_runs,
                "total_rosetta_runs": params.total_calculations
            },
            "complexity_factors": {
                "length_impact": f"{length_impact:.2f}x",
                "length_explanation": f"Length factor: ({params.peptide_length}/{PeptideCostCalculator.STANDARD_PEPTIDE_LENGTH})^{PeptideCostCalculator.COMPLEXITY_EXPONENT}",
                "total_runs_impact": f"{params.total_calculations}x"
            },
            "cost_breakdown": {
                "base_complexity": round(params.complexity_factor, 6),
                "total_iterations": params.n_iterations,
                "runs_per_iteration": params.n_rosetta_runs,
                "total_calculations": params.total_calculations
            },
            "comparison": {
                "vs_standard_single_run": f"{params.total_compute_units:.1f}x",
                "category": complexity_category,
                "equivalent_standard_runs": round(params.total_compute_units, 1)
            }
        }
    
    @staticmethod
    def estimate_execution_time(params: PeptideTaskParams, base_time_per_cu_minutes: float = 1.0) -> Dict[str, Any]:
        """
        预估执行时间
        
        Args:
            params: PeptideTaskParams对象
            base_time_per_cu_minutes: 每个计算单元的基准时间（分钟）
            
        Returns:
            时间预估信息
        """
        
        total_minutes = params.total_compute_units * base_time_per_cu_minutes
        
        # 格式化时间显示
        if total_minutes < 1:
            time_str = f"{total_minutes * 60:.0f}s"
        elif total_minutes < 60:
            time_str = f"{total_minutes:.1f}m"
        elif total_minutes < 1440:  # 小于24小时
            hours = total_minutes / 60
            time_str = f"{hours:.1f}h"
        else:  # 超过24小时
            days = total_minutes / 1440
            time_str = f"{days:.1f}d"
        
        return {
            "estimated_time": time_str,
            "total_minutes": round(total_minutes, 2),
            "total_hours": round(total_minutes / 60, 2),
            "breakdown": {
                "per_iteration": round(total_minutes / params.n_iterations, 2),
                "per_rosetta_run": round(total_minutes / params.total_calculations, 2)
            },
            "note": "Estimation based on standard hardware (Rosetta ddG calculations)"
        }

    @staticmethod
    def estimate_cost_before_submission(
        peptide_sequence: str,
        n_iterations: int,
        n_rosetta_runs: int,
        receptor_pdb_filename: str = "preview.pdb",
        num_seq_per_target: int = 10,
        proteinmpnn_seed: int = 37
    ) -> Dict[str, Any]:
        """
        在提交任务前进行成本预估（不保存到数据库）
        
        Returns:
            预估成本信息
        """
        
        # 计算成本因子
        cost_factors = PeptideCostCalculator.calculate_cost_factors(
            peptide_sequence=peptide_sequence,
            n_iterations=n_iterations,
            n_rosetta_runs=n_rosetta_runs
        )
        
        # 创建临时参数对象用于生成摘要
        temp_params = PeptideTaskParams(
            id="preview",
            task_id="preview", 
            peptide_sequence=peptide_sequence,
            peptide_length=cost_factors["peptide_length"],
            receptor_pdb_filename=receptor_pdb_filename,
            n_iterations=n_iterations,
            n_rosetta_runs=n_rosetta_runs,
            num_seq_per_target=num_seq_per_target,
            proteinmpnn_seed=proteinmpnn_seed,
            total_calculations=cost_factors["total_calculations"],
            complexity_factor=cost_factors["complexity_factor"],
            total_compute_units=cost_factors["total_compute_units"],
            created_at=datetime.now()
        )
        
        # 生成成本摘要
        cost_summary = PeptideCostCalculator.get_cost_estimate_summary(temp_params)
        
        # 生成时间预估
        time_estimate = PeptideCostCalculator.estimate_execution_time(temp_params)
        
        return {
            "task_id": "preview",
            "is_preview": True,
            **cost_summary,
            "time_estimate": time_estimate
        }
