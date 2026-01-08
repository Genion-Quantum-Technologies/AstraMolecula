"""
存储服务模块

提供统一的对象存储接口，使用 SeaweedFS 作为后端。

使用示例:
    from services.storage import get_storage
    
    storage = get_storage()
    
    # 上传文件
    await storage.upload_file(local_path, "uploads/user_id/file.pdb")
    
    # 上传字节数据
    await storage.upload_bytes(content, "uploads/user_id/file.pdb")
    
    # 下载文件
    await storage.download_file("uploads/user_id/file.pdb", local_path)
    
    # 生成预签名 URL
    url = await storage.get_presigned_url("uploads/user_id/file.pdb")
    
    # 检查文件是否存在
    exists = await storage.file_exists("uploads/user_id/file.pdb")
    
    # 列出文件
    files = await storage.list_files("uploads/user_id/")
    
    # 删除文件
    await storage.delete_file("uploads/user_id/file.pdb")
"""
import logging
from typing import Optional

from .seaweed_storage import SeaweedStorage
from config import storage as storage_config

logger = logging.getLogger("storage")

_storage_instance: Optional[SeaweedStorage] = None


def get_storage() -> SeaweedStorage:
    """
    获取 SeaweedFS 存储实例（单例）
    
    Returns:
        SeaweedStorage 实例
    """
    global _storage_instance
    
    if _storage_instance is None:
        logger.info("Initializing SeaweedFS storage...")
        _storage_instance = SeaweedStorage()
    
    return _storage_instance


def reset_storage():
    """
    重置存储实例（主要用于测试）
    """
    global _storage_instance
    _storage_instance = None


__all__ = ['get_storage', 'reset_storage', 'SeaweedStorage', 'storage_config']
