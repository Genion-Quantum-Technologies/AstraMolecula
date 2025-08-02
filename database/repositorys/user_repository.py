from database.db import get_connection
from database.models.user import User
from typing import List, Optional
from datetime import datetime

class UserRepository:
    @staticmethod
    def create(uuid: str, username: str, password_hash: str, phone: str = None, email: str = None) -> None:
        sql = """
        INSERT INTO users (id, username, password_hash, phone, email)
        VALUES (%s, %s, %s, %s, %s)
        """
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (uuid, username, password_hash, phone, email))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_by_username(username: str) -> Optional[User]:
        sql = """
        SELECT id, username, password_hash, phone, email, created_at, updated_at,
               external_user_id, source_system, created_by_service, is_shadow_user, migrated_to
          FROM users
         WHERE username = %s
        """
        conn = get_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (username,))
                row = cur.fetchone()
            if row:
                return User(**row)
        finally:
            conn.close()
        return None

    @staticmethod
    def list_all(limit: int = 100) -> List[User]:
        sql = """
        SELECT id, username, password_hash, phone, email, created_at, updated_at,
               external_user_id, source_system, created_by_service, is_shadow_user, migrated_to
          FROM users
      ORDER BY created_at DESC
         LIMIT %s
        """
        conn = get_connection()
        users = []
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (limit,))
                for row in cur.fetchall():
                    users.append(User(**row))
        finally:
            conn.close()
        return users

    @staticmethod
    def update_password(username: str, new_hash: str) -> None:
        sql = "UPDATE users SET password_hash = %s WHERE username = %s"
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (new_hash, username))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def update_contact(username: str, phone: str = None, email: str = None) -> None:
        parts, args = [], []
        if phone is not None:
            parts.append("phone = %s")
            args.append(phone)
        if email is not None:
            parts.append("email = %s")
            args.append(email)
        if not parts:
            return
        args.append(username)
        sql = f"UPDATE users SET {', '.join(parts)} WHERE username = %s"
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(args))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def delete(username: str) -> None:
        sql = "DELETE FROM users WHERE username = %s"
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (username,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_by_id(user_id: str) -> Optional[User]:
        """根据用户ID获取用户"""
        sql = """
        SELECT id, username, password_hash, phone, email, created_at, updated_at,
               external_user_id, source_system, created_by_service, is_shadow_user, migrated_to
          FROM users
         WHERE id = %s
        """
        conn = get_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (user_id,))
                row = cur.fetchone()
            if row:
                return User(**row)
        finally:
            conn.close()
        return None

    @staticmethod
    def create_shadow_user(user_id: str, username: str, password_hash: str, email: str,
                          external_user_id: str, source_system: str, created_by_service: str,
                          is_shadow_user: bool = True) -> None:
        """创建影子用户"""
        sql = """
        INSERT INTO users (id, username, password_hash, email, external_user_id, 
                          source_system, created_by_service, is_shadow_user)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, username, password_hash, email, 
                                external_user_id, source_system, created_by_service, is_shadow_user))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_shadow_user(external_user_id: str, service_name: str) -> Optional[User]:
        """查找影子用户"""
        sql = """
        SELECT id, username, password_hash, phone, email, created_at, updated_at,
               external_user_id, source_system, created_by_service, is_shadow_user, migrated_to
          FROM users
         WHERE external_user_id = %s AND source_system = %s AND is_shadow_user = 1
        """
        conn = get_connection()
        try:
            with conn.cursor(dictionary=True) as cur:
                cur.execute(sql, (external_user_id, service_name))
                row = cur.fetchone()
            if row:
                return User(**row)
        finally:
            conn.close()
        return None

    @staticmethod
    def merge_shadow_user_data(shadow_user_id: str, real_user_id: str) -> None:
        """将影子用户的数据迁移到真实用户"""
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # 更新所有任务的所有者
                cur.execute(
                    "UPDATE tasks SET user_id = %s WHERE user_id = %s",
                    (real_user_id, shadow_user_id)
                )
                
                # 更新上传文件的所有者
                cur.execute(
                    "UPDATE user_uploads SET user_id = %s WHERE user_id = %s",
                    (real_user_id, shadow_user_id)
                )
                
                # 标记影子用户为已迁移
                cur.execute(
                    "UPDATE users SET migrated_to = %s WHERE id = %s",
                    (real_user_id, shadow_user_id)
                )
                
            conn.commit()
        finally:
            conn.close()
