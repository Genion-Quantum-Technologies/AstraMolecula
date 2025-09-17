from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class User:
    id: str
    username: str
    password_hash: str
    phone: Optional[str]
    email: Optional[str]
    created_at: datetime
    updated_at: datetime
    external_user_id: Optional[str] = None
    source_system: str = 'internal'
    created_by_service: Optional[str] = None
    is_shadow_user: bool = False
    migrated_to: Optional[str] = None
    user_role: str = 'user'  # 'user' or 'admin'
    is_admin: bool = False
