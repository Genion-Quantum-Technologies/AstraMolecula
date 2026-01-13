from astra_molecula.db.db import get_connection
from astra_molecula.db.models.upload import UserUpload
from typing import List, Optional
import uuid

class UploadRepository:
    @staticmethod
    def create(user_id: str, filename: str, file_path: str, 
               file_size: Optional[int] = None, content_type: Optional[str] = None) -> str:
        """创建用户上传记录，返回生成的upload_id"""
        # user_uploads表的id字段统一使用36位UUID
        upload_id = str(uuid.uuid4())
        sql = """
        INSERT INTO user_uploads (id, user_id, filename, file_path, file_size, content_type)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (upload_id, user_id, filename, file_path, file_size, content_type))
            conn.commit()
        finally:
            conn.close()
        return upload_id

    @staticmethod
    def list_by_user(user_id: str) -> List[UserUpload]:
        sql = """
        SELECT id, user_id, filename, file_path, uploaded_at, file_size, content_type
          FROM user_uploads
         WHERE user_id = %s
      ORDER BY uploaded_at DESC
        """
        conn = get_connection()
        uploads = []
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (user_id,))
                for row in cur.fetchall():
                    uploads.append(UserUpload(**row))
        finally:
            conn.close()
        return uploads

