from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ServiceUserMapping:
    id: str
    service_api_key: str
    external_user_id: str
    internal_user_id: str
    created_at: datetime
    updated_at: datetime
