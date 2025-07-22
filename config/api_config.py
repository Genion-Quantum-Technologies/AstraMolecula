# API 配置文件

# 缓存设置
CACHE_SETTINGS = {
    "file_cache_duration": 3600,  # 文件缓存1小时 (秒)
    "status_cache_duration": 60,  # 状态缓存1分钟 (秒)
}

# 轮询设置
POLLING_SETTINGS = {
    "min_interval": 2,  # 最小轮询间隔 (秒)
    "max_interval": 30,  # 最大轮询间隔 (秒)
    "backoff_factor": 1.5,  # 退避因子
}

# HTTP 状态码说明
STATUS_CODE_MEANINGS = {
    202: "task_processing",
    409: "task_status_conflict", 
    410: "task_failed",
    425: "task_pending",
}

# 任务状态优先级（用于前端决定轮询频率）
TASK_STATUS_PRIORITY = {
    "pending": 1,
    "processing": 2, 
    "finished": 0,
    "failed": 0,
}
