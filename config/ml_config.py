"""
ML 模型配置
提供对 ML 配置的兼容性访问，实际配置值从 settings.yaml 加载
"""

from config.settings import ml as _ml

# 兼容旧代码的常量格式
DATA_DEFAULT = {
    'max_sequence_length': _ml.max_sequence_length,
    'padding_value': _ml.padding_value
}

PROPERTIES = _ml.properties

# For Test_Property test
LOD_MIN = _ml.lod_min
LOD_MAX = _ml.lod_max
