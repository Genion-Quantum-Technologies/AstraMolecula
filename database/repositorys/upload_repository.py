from database.db import get_connection
from database.models.upload import UserUpload
from typing import List

class UploadRepository:
    @staticmethod
    def create(user_id: str, filename: str, file_path: str) -> None:
        sql = """
        INSERT INTO user_uploads (user_id, filename, file_path)
        VALUES (%s, %s, %s)
        """
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, filename, file_path))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def list_by_user(user_id: str) -> List[UserUpload]:
        sql = """
        SELECT id, user_id, filename, file_path, uploaded_at
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
