from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class UserMigration:
    id: str
    shadow_user_id: str
    real_user_id: str
    migration_date: datetime
    migration_type: str = 'auto_merge'  # 'auto_merge', 'manual_merge', 'account_claim'
