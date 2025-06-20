from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from fastapi.security import OAuth2PasswordBearer
from database.services.user_service import UserService

# JWT 配置
SECRET_KEY = "YOUR_RANDOM_SECRET_KEY_32+_CHARS"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

# 生成 JWT
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# ---- 依赖：解析并验证 Token ----
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exc = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    user = UserService.get_user(username)
    if not user:
        raise credentials_exc
    return user