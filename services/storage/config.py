"""
SeaweedFS 存储配置模块
"""
import os
from pathlib import Path


class StorageConfig:
    """SeaweedFS 存储配置"""
    
    # SeaweedFS 配置 - 使用 Filer API（更稳定）
    SEAWEED_FILER_ENDPOINT = os.getenv("SEAWEED_FILER_ENDPOINT", "http://localhost:8888")
    SEAWEED_BUCKET = os.getenv("SEAWEED_BUCKET", "astramolecula")
    
    # S3 API 配置（备用）
    SEAWEED_S3_ENDPOINT = os.getenv("SEAWEED_S3_ENDPOINT", "http://localhost:8333")
    SEAWEED_ACCESS_KEY = os.getenv("SEAWEED_ACCESS_KEY", "")
    SEAWEED_SECRET_KEY = os.getenv("SEAWEED_SECRET_KEY", "")
    
    # 使用哪种 API：filer 或 s3
    SEAWEED_API_TYPE = os.getenv("SEAWEED_API_TYPE", "filer")
    
    # 临时文件目录（用于计算任务的本地缓存）
    TEMP_DIR = Path(os.getenv("TEMP_DIR", "/tmp/astramolecula"))
    
    # 预签名 URL 过期时间（秒）
    PRESIGNED_URL_EXPIRES = int(os.getenv("PRESIGNED_URL_EXPIRES", "3600"))
    
    @classmethod
    def ensure_temp_dir(cls) -> Path:
        """确保临时目录存在"""
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        return cls.TEMP_DIR
    
    @classmethod
    def get_filer_base_url(cls) -> str:
        """获取 Filer 的 bucket 基础 URL"""
        return f"{cls.SEAWEED_FILER_ENDPOINT}/buckets/{cls.SEAWEED_BUCKET}"
