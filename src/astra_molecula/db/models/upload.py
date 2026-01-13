from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UserUpload:
    id: str
    user_id: str
    filename: str
    file_path: str  # 现在存储的是 SeaweedFS 的 remote_key
    uploaded_at: datetime
    file_size: Optional[int] = None  # 文件大小（字节）
    content_type: Optional[str] = None  # MIME 类型
    
    @property
    def storage_key(self) -> str:
        """返回存储键（兼容性别名）"""
        return self.file_path
