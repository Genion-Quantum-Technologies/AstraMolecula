import uuid
import bcrypt
from typing import Optional, List
from datetime import datetime

from database.models.user import User
from database.repositorys.user_repository import UserRepository
class UserService:
    @staticmethod
    def register(username: str, password: str, phone: str = None, email: str = None) -> None:
        # 1) 哈希密码
        pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        # 2) 生成 UUID
        user_id = str(uuid.uuid4())  # 生成 UUID
        # 3) 调用存储库，并传递 user_id
        UserRepository.create(user_id, username, pw_hash, phone, email)

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

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[User]:
        """根据用户ID获取用户"""
        return UserRepository.get_by_id(user_id)

    @staticmethod
    def create_shadow_user(external_user_id: str, service_api_key: str) -> User:
        """创建影子用户"""
        user_id = str(uuid.uuid4())
        username = f"shadow_{external_user_id}_{service_api_key[:8]}"
        email = f"shadow_{external_user_id}@{service_api_key[:8]}.service"
        
        # 创建一个临时密码hash，影子用户不能直接登录
        temp_password = str(uuid.uuid4())
        pw_hash = bcrypt.hashpw(temp_password.encode(), bcrypt.gensalt()).decode()
        
        # 使用扩展的参数创建用户
        UserRepository.create_shadow_user(
            user_id=user_id,
            username=username,
            password_hash=pw_hash,
            email=email,
            external_user_id=external_user_id,
            source_system=service_api_key,
            created_by_service=service_api_key,
            is_shadow_user=True
        )
        
        return UserRepository.get_by_id(user_id)

    @staticmethod
    def find_shadow_user(external_user_id: str, service_name: str) -> Optional[User]:
        """查找影子用户"""
        return UserRepository.get_shadow_user(external_user_id, service_name)

    @staticmethod
    def merge_shadow_user_to_real_user(shadow_user_id: str, real_user_id: str) -> None:
        """将影子用户的数据迁移到真实用户"""
        # 这里需要调用repository来执行数据迁移
        UserRepository.merge_shadow_user_data(shadow_user_id, real_user_id)
