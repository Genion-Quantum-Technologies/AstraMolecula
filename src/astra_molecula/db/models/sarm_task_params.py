"""
SARM 任务参数表模型
用于存储 SARM 矩阵分析和 SAR 树生成任务的参数
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class SarmTaskParams(BaseModel):
    """
    SARM 任务参数表模型
    
    task_subtype 区分两种任务类型:
    - 'sarm': SARM 矩阵生成
    - 'tree': SAR 树生成
    """
    id: str                                    # 主键 CHAR(32)
    task_id: str                               # 关联的任务ID CHAR(36)
    task_subtype: str = "sarm"                 # 'sarm' 或 'tree'

    # ---- SARM 矩阵生成参数 (task_subtype = 'sarm') ----
    csv_filename: Optional[str] = "compounds.csv"       # CSV 文件名
    analysis_type: Optional[str] = "smiles"              # 'smiles' 或 'scaffold'
    value_columns: Optional[str] = "[]"                  # JSON 数组，如 '["IC50", "Ki"]'
    log_transform: Optional[bool] = False                # 是否对活性值取对数
    minimum_site1: Optional[float] = 3                   # Site1 最小计数
    minimum_site2: Optional[float] = 3                   # Site2 最小计数
    n_jobs: Optional[int] = None                         # 并行任务数
    csv2excel: Optional[bool] = False                    # 是否导出 Excel

    # ---- SAR 树生成参数 (task_subtype = 'tree') ----
    fragment_core: Optional[str] = None                  # 核心片段 SMARTS/SMILES
    root_title: Optional[str] = None                     # 根节点显示名称
    input_file: Optional[str] = "input.csv"              # 树输入数据文件名
    tree_content: Optional[str] = '["double-cut"]'       # JSON 数组，树中展示的内容类型
    highlight_dict: Optional[str] = "[]"                 # JSON 数组，高亮配置
    max_level: Optional[int] = 5                         # 树的最大展开层数

    # ---- 时间戳 ----
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
