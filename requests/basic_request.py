from typing import Optional
from pydantic import BaseModel, EmailStr

class UserCreateRequest(BaseModel):
    username: str
    password: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class UserLoginRequest(BaseModel):
    username: str
    password: str