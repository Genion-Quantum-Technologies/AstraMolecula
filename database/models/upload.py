from dataclasses import dataclass
from datetime import datetime

@dataclass
class UserUpload:
    id: str
    user_id: str
    filename: str
    file_path: str
    uploaded_at: datetime
