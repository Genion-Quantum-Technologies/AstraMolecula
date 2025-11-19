import logging
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from jose import JWTError, jwt

from database.services.user_service import UserService
from database.services.service_user_mapping_service import ServiceUserMappingService
from security.auth import ALGORITHM, SECRET_KEY, SERVICE_API_KEYS

logger = logging.getLogger("middleware")

# 你想要跳过验证的路径列表
OPEN_PATHS = {
    "/",
    "/login",
    "/signup",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/smiles2img",
    "/fragmentize",
    "/logs",
    "/logs/",
}

# 高优先级路径列表（tasks相关接口）
HIGH_PRIORITY_PATHS = {
    "/tasks",
    "/tasks/",
}

# 开放路径前缀列表（需要前缀匹配的路径）
OPEN_PATH_PREFIXES = {
    "/logs",
    "/static",
    "/public",  # 公开访问路径（无需认证）
}

def is_high_priority_request(path: str) -> bool:
    """检查是否为高优先级请求"""
    return any(path.startswith(hp) for hp in HIGH_PRIORITY_PATHS)

async def get_or_create_service_user(api_key: str, external_user_id: str):
    """获取或创建服务用户映射"""
    # 首先查找现有映射
    mapping = ServiceUserMappingService.get_mapping(api_key, external_user_id)
    
    if mapping:
        user = UserService.get_user_by_id(mapping.internal_user_id)
        if user:
            return user
    
    # 创建影子用户
    shadow_user = UserService.create_shadow_user(
        external_user_id=external_user_id,
        service_api_key=api_key
    )
    
    # 创建映射
    ServiceUserMappingService.create_mapping(
        service_api_key=api_key,
        external_user_id=external_user_id,
        internal_user_id=shadow_user.id
    )
    
    return shadow_user

async def auth_middleware(request: Request, call_next):
    """认证中间件，提供详细的错误响应和高优先级处理"""
    try:
        # 检查是否为高优先级请求
        is_high_priority = is_high_priority_request(request.url.path)
        
        if is_high_priority:
            logger.debug("High priority request: %s %s", request.method, request.url.path)
        else:
            logger.debug("Processing request: %s %s", request.method, request.url.path)
        
        if request.method == "OPTIONS":
            logger.debug("Handling OPTIONS request for %s", request.url.path)
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
            return response

        if request.url.path in OPEN_PATHS or any(request.url.path.startswith(prefix) for prefix in OPEN_PATH_PREFIXES):
            logger.debug("Open path accessed: %s", request.url.path)
            response = await call_next(request)
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
            return response

        api_key = request.headers.get("X-API-Key")
        if api_key:
            if api_key in SERVICE_API_KEYS:
                # 获取外部用户ID
                external_user_id = request.headers.get("X-External-User-ID")
                if not external_user_id:
                    logger.warning("API key request missing X-External-User-ID header")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "Missing external user ID",
                            "message": "X-External-User-ID header is required for service authentication",
                            "suggestion": "Please provide the external user ID in the X-External-User-ID header",
                            "error_code": "AUTH_MISSING_EXTERNAL_USER_ID"
                        },
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                            "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
                        }
                    )
                
                # 查找或创建用户映射
                try:
                    user = await get_or_create_service_user(api_key, external_user_id)
                    
                    if is_high_priority:
                        logger.debug("High priority API key request: %s for user %s", 
                                   request.url.path, external_user_id)
                    else:
                        logger.debug("Valid API key used for %s for user %s", 
                                   request.url.path, external_user_id)
                    
                    request.state.service = api_key
                    request.state.user = user
                    request.state.auth_type = 'service'
                    request.state.external_user_id = external_user_id
                    
                    response = await call_next(request)
                    response.headers["Access-Control-Allow-Origin"] = "*"
                    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
                    response.headers["Access-Control-Allow-Headers"] = "Authorization, X-API-Key, Content-Type"
                    
                    # 为高优先级请求添加特殊头部
                    if is_high_priority:
                        response.headers["X-Priority"] = "high"
                        response.headers["Cache-Control"] = "no-cache, must-revalidate"
                    
                    return response
                    
                except Exception as e:
                    logger.error("Error in service user mapping: %s", str(e))
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "Service authentication error",
                            "message": "Failed to process service authentication",
                            "error_code": "AUTH_SERVICE_ERROR"
                        },
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                            "Access-Control-Allow-Headers": "Authorization, X-API-Key, Content-Type"
                        }
                    )
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
        request.state.auth_type = 'user'
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
