from fastapi import HTTPException, Request
from jose import JWTError, jwt

from database.services.user_service import UserService
from security.auth import ALGORITHM, SECRET_KEY, SERVICE_API_KEYS

# 你想要跳过验证的路径列表
OPEN_PATHS = {
    "/login",
    "/signup",         
}

async def auth_middleware(request: Request, call_next):
    if request.url.path in OPEN_PATHS:
        return await call_next(request)

    api_key = request.headers.get("X-API-Key")
    if api_key:
        if api_key in SERVICE_API_KEYS:
            request.state.service = api_key
            return await call_next(request)
        raise HTTPException(401, "Invalid API key")

    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = auth.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    user = UserService.get_user(username)
    if not user:
        raise HTTPException(401, "User not found")

    request.state.user = user
    return await call_next(request)