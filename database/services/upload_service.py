from typing import List
from database.models.upload import UserUpload
from database.repositorys.upload_repository import UploadRepository

class UploadService:
    @staticmethod
    def record_upload(user_id: str, filename: str, file_path: str) -> str:
        """记录用户上传，返回upload_id"""
        return UploadRepository.create(user_id, filename, file_path)

    @staticmethod
    def list_by_user(user_id: str) -> List[UserUpload]:
        """
        返回指定用户的所有上传记录
        """
        return UploadRepository.list_by_user(user_id)