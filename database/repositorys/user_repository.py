from database.db import get_connection
from database.models.user import User
from typing import List, Optional

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
        SELECT id, username, password_hash, phone, email, created_at, updated_at
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
        SELECT id, username, password_hash, phone, email, created_at, updated_at
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
