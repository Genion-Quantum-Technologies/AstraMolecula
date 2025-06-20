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
