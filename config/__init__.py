"""
配置模块
"""

# 直接在这里定义ROOT，避免循环导入
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent

# 延迟导入避免循环依赖
def setup_logging(level="INFO"):
    from .logging_config import setup_logging as _setup_logging
    return _setup_logging(level, ROOT)

def get_module_logger(module_name):
    from .logging_config import get_module_logger as _get_module_logger
    return _get_module_logger(module_name)

__all__ = ['ROOT', 'setup_logging', 'get_module_logger']
