"""
SARM 任务参数服务类
业务逻辑层，处理 SARM 任务参数的创建、查询等操作
"""
import json
import uuid
import logging
from typing import Optional, List

from astra_molecula.db.models.sarm_task_params import SarmTaskParams
from astra_molecula.db.repositories.sarm_task_params_repository import SarmTaskParamsRepository

logger = logging.getLogger("sarm_task_params_service")


class SarmTaskParamsService:
    """SARM 任务参数服务类"""

    @staticmethod
    def create_sarm_params(
        task_id: str,
        csv_filename: str,
        value_columns: List[str],
        analysis_type: str = "smiles",
        log_transform: bool = False,
        minimum_site1: float = 3,
        minimum_site2: float = 3,
        n_jobs: Optional[int] = None,
        csv2excel: bool = False
    ) -> SarmTaskParams:
        """
        创建 SARM 矩阵生成任务参数

        Args:
            task_id: 关联的任务 ID
            csv_filename: CSV 文件名
            value_columns: 活性列名列表
            analysis_type: 分析类型 ('smiles' 或 'scaffold')
            log_transform: 是否对数变换
            minimum_site1: Site1 最小计数
            minimum_site2: Site2 最小计数
            n_jobs: 并行进程数
            csv2excel: 是否导出 Excel

        Returns:
            创建的 SarmTaskParams 对象
        """
        logger.info("Creating SARM analysis params for task %s", task_id)

        # 确保表存在
        SarmTaskParamsRepository.create_table_if_not_exists()

        param_id = uuid.uuid4().hex  # 32 位 hex

        params = SarmTaskParams(
            id=param_id,
            task_id=task_id,
            task_subtype="sarm",
            csv_filename=csv_filename,
            analysis_type=analysis_type,
            value_columns=json.dumps(value_columns),
            log_transform=log_transform,
            minimum_site1=minimum_site1,
            minimum_site2=minimum_site2,
            n_jobs=n_jobs,
            csv2excel=csv2excel
        )

        SarmTaskParamsRepository.create(params)
        logger.info("SARM analysis params created: id=%s, task_id=%s, value_columns=%s",
                    param_id, task_id, value_columns)
        return params

    @staticmethod
    def create_tree_params(
        task_id: str,
        fragment_core: str,
        root_title: str,
        input_file: str = "input.csv",
        tree_content: Optional[List[str]] = None,
        highlight_dict: Optional[List[str]] = None,
        max_level: int = 5
    ) -> SarmTaskParams:
        """
        创建 SAR 树生成任务参数

        Args:
            task_id: 关联的任务 ID
            fragment_core: 核心片段 SMARTS/SMILES
            root_title: 根节点显示名称
            input_file: 输入数据文件名
            tree_content: 树中展示的内容类型
            highlight_dict: 高亮配置列表
            max_level: 最大展开层数

        Returns:
            创建的 SarmTaskParams 对象
        """
        logger.info("Creating SAR tree params for task %s", task_id)

        # 确保表存在
        SarmTaskParamsRepository.create_table_if_not_exists()

        if tree_content is None:
            tree_content = ["double-cut"]
        if highlight_dict is None:
            highlight_dict = []

        param_id = uuid.uuid4().hex

        params = SarmTaskParams(
            id=param_id,
            task_id=task_id,
            task_subtype="tree",
            fragment_core=fragment_core,
            root_title=root_title,
            input_file=input_file,
            tree_content=json.dumps(tree_content),
            highlight_dict=json.dumps(highlight_dict),
            max_level=max_level
        )

        SarmTaskParamsRepository.create(params)
        logger.info("SAR tree params created: id=%s, task_id=%s, fragment_core=%s",
                    param_id, task_id, fragment_core)
        return params

    @staticmethod
    def get_task_params(task_id: str) -> Optional[SarmTaskParams]:
        """
        获取任务参数

        Args:
            task_id: 任务 ID

        Returns:
            SarmTaskParams 对象，如果不存在返回 None
        """
        try:
            return SarmTaskParamsRepository.get_by_task_id(task_id)
        except Exception as e:
            logger.error("Failed to get sarm task params for task %s: %s", task_id, e)
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
        logger.info("Deleting SARM task params for task %s", task_id)
        return SarmTaskParamsRepository.delete_by_task_id(task_id)
