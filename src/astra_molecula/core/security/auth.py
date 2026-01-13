from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from fastapi.security import OAuth2PasswordBearer

from astra_molecula.db.services.user_service import UserService
from astra_molecula.db.models.user import User
from astra_molecula.core.config import security as security_config

# JWT 配置（从统一配置加载）
SECRET_KEY = security_config.jwt_secret_key
ALGORITHM = security_config.jwt_algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = security_config.access_token_expire_minutes

# 服务间 API Keys（从统一配置加载）
SERVICE_API_KEYS = security_config.service_api_keys

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

# ---- 管理员权限验证 ----
async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    获取当前管理员用户，如果不是管理员则抛出权限错误
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required"
        )
    return current_user

# ---- 管理员或本人权限验证 ----
def get_admin_or_self_user(user_id: str):
    """
    创建一个依赖函数，验证用户是管理员或者是资源的所有者
    """
    async def verify_access(current_user: User = Depends(get_current_user)) -> User:
        if current_user.is_admin or current_user.id == user_id:
            return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Administrator or resource owner access required"
        )
    return verify_access