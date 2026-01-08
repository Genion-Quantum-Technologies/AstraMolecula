"""
API 配置文件
从 settings.yaml 加载配置，保持向后兼容
"""

from config.settings import api as _api

# 缓存设置 (兼容旧代码)
CACHE_SETTINGS = {
    "file_cache_duration": _api.file_cache_duration,
    "status_cache_duration": _api.status_cache_duration,
}

# 轮询设置 (兼容旧代码)
POLLING_SETTINGS = {
    "min_interval": _api.polling_min_interval,
    "max_interval": _api.polling_max_interval,
    "backoff_factor": _api.polling_backoff_factor,
}

# HTTP 状态码说明 (静态常量)
STATUS_CODE_MEANINGS = {
    202: "task_processing",
    409: "task_status_conflict", 
    410: "task_failed",
    425: "task_pending",
}

# 任务状态优先级 (静态常量)
TASK_STATUS_PRIORITY = {
    "pending": 1,
    "processing": 2, 
    "finished": 0,
    "failed": 0,
}
