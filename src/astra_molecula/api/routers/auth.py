
import logging
from fastapi import APIRouter, HTTPException, Depends
from astra_molecula.db.services.user_service import UserService
from astra_molecula.db.models.user import User
from astra_molecula.schemas.requests.basic_request import UserCreateRequest, UserLoginRequest
from astra_molecula.core.security.auth import TokenResponse, create_access_token, get_current_user

logger = logging.getLogger("auth_router")
router = APIRouter(prefix="", tags=["Auth"])

@router.post("/login", response_model=TokenResponse)
async def login_for_token(request: UserLoginRequest):
    """
    登录接口：校验用户名/密码，成功后返回 JWT
    """
    logger.info("Login attempt for username: %s", request.username)
    
    if not UserService.authenticate(request.username, request.password):
        logger.warning("Failed login attempt for username: %s", request.username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 载荷中放 sub = username，也可以放 user_id
    access_token = create_access_token(
        data={"sub": request.username}
    )
    logger.info("Successful login for username: %s", request.username)
    return {"access_token": access_token}

@router.post("/signup", status_code=201)
async def signup_user(request: UserCreateRequest):
    """
    创建一个新用户。
    """
    logger.info("Signup attempt for username: %s, email: %s", 
                request.username, request.email)
    try:
        # 调用业务层做注册
        UserService.register(
            username=request.username,
            password=request.password,
            phone=request.phone,
            email=request.email
        )
        return {"message": "User created successfully"}
    except Exception as e:
        # 你可以根据不同的异常类型返回不同的 status_code
        raise HTTPException(status_code=500, detail=f"Failed to create user: {e}")

@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户的信息
    """
    logger.info("User %s requesting own info", current_user.username)
    
    # 返回用户信息，排除敏感字段
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "phone": current_user.phone,
        "user_role": current_user.user_role,
        "is_admin": current_user.is_admin,
        "is_shadow_user": current_user.is_shadow_user,
        "source_system": current_user.source_system,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at
    }
