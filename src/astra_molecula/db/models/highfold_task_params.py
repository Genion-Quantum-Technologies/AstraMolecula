"""
HighFold-C2C 任务参数表模型
用于存储环肽设计与结构预测任务的参数
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class HighFoldTaskParams(BaseModel):
    """
    HighFold-C2C 任务参数表模型

    三阶段 pipeline 参数:
    - Stage 1 — C2C 序列生成: core_sequence, span_len, num_sample, temperature, top_p, seed
    - Stage 2 — HighFold 结构预测: model_type, msa_mode, disulfide_bond_pairs, num_models, num_recycle, use_templates, amber, num_relax
    - Stage 3 — 理化性质评估: 无额外输入
    """
    id: str                                                  # 主键 CHAR(32)
    task_id: str                                             # 关联的任务ID CHAR(36)

    # ---- C2C 序列生成参数 (Stage 1) ----
    core_sequence: Optional[str] = None                      # 核心肽段序列（用户必填）
    span_len: int = 5                                        # 延伸长度（每侧）
    num_sample: int = 20                                     # 采样数量
    temperature: float = 1.0                                 # 采样温度
    top_p: float = 0.9                                       # 核采样阈值
    seed: int = 42                                           # 随机种子

    # ---- HighFold 结构预测参数 (Stage 2) ----
    model_type: str = "alphafold2"                           # 模型类型
    msa_mode: str = "single_sequence"                        # MSA 搜索模式
    disulfide_bond_pairs: Optional[str] = None               # 二硫键位置对，格式 "A,B" 或 "A,B:C,D"
    num_models: int = 5                                      # 预测模型数量 (1-5)
    num_recycle: Optional[int] = None                        # 循环次数
    use_templates: bool = False                              # 是否使用模板
    amber: bool = False                                      # AMBER 精修
    num_relax: int = 0                                       # 精修结构数

    # ---- 阶段控制参数 ----
    skip_generate: bool = False                              # 跳过 C2C 序列生成
    skip_predict: bool = False                               # 跳过结构预测
    skip_evaluate: bool = False                              # 跳过评估阶段

    # ---- 时间戳 ----
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
