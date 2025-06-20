import bcrypt
from typing import Optional, List

from database.models.user import User
from database.repositorys.user_repository import UserRepository
class UserService:
    @staticmethod
    def register(username: str, password: str, phone: str = None, email: str = None) -> None:
        # 1) 哈希密码
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        # 2) 调用存储库
        UserRepository.create(username, pw_hash, phone, email)

    @staticmethod
    def authenticate(username: str, password: str) -> bool:
        user: Optional[User] = UserRepository.get_by_username(username)
        if not user:
            return False
        return bcrypt.checkpw(password.encode(), user.password_hash.encode())

    @staticmethod
    def get_user(username: str) -> Optional[User]:
        """
        根据 username 返回 User 对象（或 None）
        """
        return UserRepository.get_by_username(username)

    @staticmethod
    def list_users(limit: int = 100) -> List[User]:
        return UserRepository.list_all(limit)

    @staticmethod
    def change_password(username: str, new_password: str) -> None:
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        UserRepository.update_password(username, new_hash)

    @staticmethod
    def update_contact(username: str, phone: str = None, email: str = None) -> None:
        UserRepository.update_contact(username, phone, email)

    @staticmethod
    def remove_user(username: str) -> None:
        UserRepository.delete(username)
