
from fastapi import APIRouter, HTTPException
from database.services.user_service import UserService
from requests.basic_request import UserCreateRequest, UserLoginRequest
from security.auth import TokenResponse, create_access_token

router = APIRouter(prefix="", tags=["Auth"])

@router.post("/login", response_model=TokenResponse)
async def login_for_token(request: UserLoginRequest):
    """
    登录接口：校验用户名/密码，成功后返回 JWT
    """
    if not UserService.authenticate(request.username, request.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 载荷中放 sub = username，也可以放 user_id
    access_token = create_access_token(
        data={"sub": request.username}
    )
    return {"access_token": access_token}

@router.post("/signup", status_code=201)
async def signup_user(request: UserCreateRequest):
    """
    创建一个新用户。
    """
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
