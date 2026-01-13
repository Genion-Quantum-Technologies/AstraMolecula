from typing import List, Optional
from astra_molecula.db.models.upload import UserUpload
from astra_molecula.db.repositories.upload_repository import UploadRepository

class UploadService:
    @staticmethod
    def record_upload(user_id: str, filename: str, file_path: str,
                      file_size: Optional[int] = None, content_type: Optional[str] = None) -> str:
        """记录用户上传，返回upload_id"""
        return UploadRepository.create(user_id, filename, file_path, file_size, content_type)

    @staticmethod
    def list_by_user(user_id: str) -> List[UserUpload]:
        """
        返回指定用户的所有上传记录
        """
        return UploadRepository.list_by_user(user_id)