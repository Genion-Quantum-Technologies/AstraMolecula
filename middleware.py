import logging
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt

from database.services.user_service import UserService
from security.auth import ALGORITHM, SECRET_KEY, SERVICE_API_KEYS

logger = logging.getLogger("middleware")

# 你想要跳过验证的路径列表
OPEN_PATHS = {
    "/login",
    "/signup",         
}

async def auth_middleware(request: Request, call_next):
    """认证中间件，提供详细的错误响应"""
    try:
        logger.debug("Processing request: %s %s", request.method, request.url.path)
        
        if request.method == "OPTIONS":
            logger.debug("Handling OPTIONS request for %s", request.url.path)
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
            return response

        if request.url.path in OPEN_PATHS:
            logger.debug("Open path accessed: %s", request.url.path)
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
            return response

        api_key = request.headers.get("X-API-Key")
        if api_key:
            if api_key in SERVICE_API_KEYS:
                logger.debug("Valid API key used for %s", request.url.path)
                request.state.service = api_key
                response = await call_next(request)
                response.headers["Access-Control-Allow-Origin"] = "*"
                response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
                return response
            logger.warning("Invalid API key attempted: %s", api_key[:10] + "...")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid API key",
                    "message": "The provided API key is not valid or has expired.",
                    "suggestion": "Please check your API key or contact the administrator for a new one.",
                    "error_code": "AUTH_INVALID_API_KEY"
                },
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
                }
            )

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            logger.warning("Unauthenticated request to protected path: %s", request.url.path)
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Authentication required",
                    "message": "This endpoint requires authentication. Please provide a valid Bearer token or API key.",
                    "suggestion": "Include 'Authorization: Bearer <token>' header or 'X-API-Key: <key>' header in your request.",
                    "available_auth_methods": [
                        "Bearer token (JWT): Add 'Authorization: Bearer <your_jwt_token>' header",
                        "API key: Add 'X-API-Key: <your_api_key>' header"
                    ],
                    "open_endpoints": list(OPEN_PATHS),
                    "error_code": "AUTH_MISSING_CREDENTIALS"
                },
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
                }
            )
        token = auth.removeprefix("Bearer ").strip()

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username = payload.get("sub")
        except JWTError as e:
            logger.warning("Invalid JWT token for path %s: %s", request.url.path, str(e))
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Invalid token",
                    "message": "The provided JWT token is invalid, expired, or malformed.",
                    "suggestion": "Please login again to get a new token or check if your token is correctly formatted.",
                    "error_code": "AUTH_INVALID_TOKEN",
                    "token_error": str(e)
                },
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
                }
            )

        user = UserService.get_user(username)
        if not user:
            logger.warning("User not found for username: %s", username)
            return JSONResponse(
                status_code=401,
                content={
                    "error": "User not found",
                    "message": f"User '{username}' not found in the system.",
                    "suggestion": "Please check if your account exists or contact the administrator.",
                    "error_code": "AUTH_USER_NOT_FOUND"
                },
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
                }
            )

        request.state.user = user
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
        return response
    
    except Exception as e:
        logger.exception("Unexpected error in auth middleware: %s", e)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Authentication middleware error",
                "message": "An unexpected error occurred during authentication.",
                "suggestion": "Please try again or contact the administrator if this error persists.",
                "error_code": "AUTH_MIDDLEWARE_ERROR"
            },
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
            }
        )
