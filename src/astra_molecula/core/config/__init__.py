"""
配置模块
统一配置入口
"""

from pathlib import Path

# 项目根目录 (src/astra_molecula/core/config 的上四级到项目根目录)
ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

# 延迟导入避免循环依赖
def setup_logging(level=None):
    """设置日志系统，level 默认从 settings.yaml 读取"""
    from .logging_config import setup_logging as _setup_logging
    from .settings import logging_config as log_cfg
    if level is None:
        level = log_cfg.level
    log_file = log_cfg.file  # 从配置文件读取日志文件路径，可能为 None
    return _setup_logging(level, log_file)

def get_module_logger(module_name):
    from .logging_config import get_module_logger as _get_module_logger
    return _get_module_logger(module_name)

# 导出设置访问器
from .settings import get_settings, get, reload_settings
from .settings import server, cors, database, security, storage, api, logging_config, ml

# 兼容性导出 (原 configuration 模块)
from . import ml_config
from . import cli_opts
from . import database_config

__all__ = [
    'ROOT', 
    'setup_logging', 
    'get_module_logger',
    'get_settings',
    'get',
    'reload_settings',
    # 配置对象
    'server',
    'cors',
    'database',
    'security',
    'storage',
    'api', 
    'logging_config',
    'ml',
    # 兼容性模块
    'ml_config',
    'cli_opts',
    'database_config',
]
