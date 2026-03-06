"""
HighFold-C2C 任务参数服务类
业务逻辑层，处理 HighFold-C2C 任务参数的创建、查询等操作
"""
import uuid
import logging
from typing import Optional

from astra_molecula.db.models.highfold_task_params import HighFoldTaskParams
from astra_molecula.db.repositories.highfold_task_params_repository import HighFoldTaskParamsRepository

logger = logging.getLogger("highfold_task_params_service")


class HighFoldTaskParamsService:
    """HighFold-C2C 任务参数服务类"""

    @staticmethod
    def create_task_params(
        task_id: str,
        core_sequence: Optional[str] = None,
        span_len: int = 5,
        num_sample: int = 20,
        temperature: float = 1.0,
        top_p: float = 0.9,
        seed: int = 42,
        model_type: str = "alphafold2",
        msa_mode: str = "single_sequence",
        disulfide_bond_pairs: Optional[str] = None,
        num_models: int = 5,
        num_recycle: Optional[int] = None,
        use_templates: bool = False,
        amber: bool = False,
        num_relax: int = 0,
        skip_generate: bool = False,
        skip_predict: bool = False,
        skip_evaluate: bool = False,
    ) -> HighFoldTaskParams:
        """
        创建 HighFold-C2C 任务参数

        Args:
            task_id: 关联的任务 ID
            core_sequence: 核心肽段序列
            span_len: 延伸长度（每侧）
            num_sample: 采样数量
            temperature: 采样温度
            top_p: 核采样阈值
            seed: 随机种子
            model_type: 结构预测模型类型
            msa_mode: MSA 搜索模式
            disulfide_bond_pairs: 二硫键位置对
            num_models: 预测模型数量
            num_recycle: 循环次数
            use_templates: 是否使用模板
            amber: AMBER 精修
            num_relax: 精修结构数
            skip_generate: 跳过序列生成
            skip_predict: 跳过结构预测
            skip_evaluate: 跳过评估

        Returns:
            创建的 HighFoldTaskParams 对象
        """
        logger.info("Creating HighFold-C2C task params for task %s, core=%s, span=%d, samples=%d",
                     task_id, core_sequence, span_len, num_sample)

        # 确保表存在
        HighFoldTaskParamsRepository.create_table_if_not_exists()

        param_id = uuid.uuid4().hex  # 32 位 hex

        params = HighFoldTaskParams(
            id=param_id,
            task_id=task_id,
            core_sequence=core_sequence,
            span_len=span_len,
            num_sample=num_sample,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            model_type=model_type,
            msa_mode=msa_mode,
            disulfide_bond_pairs=disulfide_bond_pairs,
            num_models=num_models,
            num_recycle=num_recycle,
            use_templates=use_templates,
            amber=amber,
            num_relax=num_relax,
            skip_generate=skip_generate,
            skip_predict=skip_predict,
            skip_evaluate=skip_evaluate,
        )

        HighFoldTaskParamsRepository.create(params)
        logger.info("HighFold-C2C task params created: id=%s, task_id=%s", param_id, task_id)
        return params

    @staticmethod
    def get_task_params(task_id: str) -> Optional[HighFoldTaskParams]:
        """
        获取任务参数

        Args:
            task_id: 任务 ID

        Returns:
            HighFoldTaskParams 对象，如果不存在返回 None
        """
        try:
            return HighFoldTaskParamsRepository.get_by_task_id(task_id)
        except Exception as e:
            logger.error("Failed to get highfold task params for task %s: %s", task_id, e)
            return None

    @staticmethod
    def delete_task_params(task_id: str) -> bool:
        """
        删除任务参数

        Args:
            task_id: 任务 ID

        Returns:
            删除是否成功
        """
        logger.info("Deleting HighFold-C2C task params for task %s", task_id)
        return HighFoldTaskParamsRepository.delete_by_task_id(task_id)
