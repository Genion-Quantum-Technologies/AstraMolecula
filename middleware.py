from fastapi import HTTPException, Request, Response
from jose import JWTError, jwt

from database.services.user_service import UserService
from security.auth import ALGORITHM, SECRET_KEY, SERVICE_API_KEYS

# 你想要跳过验证的路径列表
OPEN_PATHS = {
    "/login",
    "/signup",         
}

async def auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
        return response

    if request.url.path in OPEN_PATHS or request.url.path.startswith("/static") or request.url.path in ["/", "/health", "/docs", "/openapi.json"]:
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
        return response

    api_key = request.headers.get("X-API-Key")
    if api_key:
        if api_key in SERVICE_API_KEYS:
            request.state.service = api_key
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
            return response
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
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
    return response
