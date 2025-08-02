from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from database.services.user_service import UserService
from database.services.service_user_mapping_service import ServiceUserMappingService
from database.services.task_service import TaskService

router = APIRouter(prefix="/user-migration", tags=["User Migration"])

class AccountClaimRequest(BaseModel):
    external_user_id: str
    service_name: str

class MigrationStatusResponse(BaseModel):
    has_shadow_account: bool
    shadow_user_id: Optional[str] = None
    task_count: int = 0
    can_migrate: bool = False

@router.post("/claim-account")
async def claim_shadow_account(request: Request, claim_request: AccountClaimRequest):
    """用户声明自己的影子账户，将数据迁移到当前账户"""
    if not hasattr(request.state, 'user') or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = request.state.user
    
    if getattr(current_user, 'is_shadow_user', False):
        raise HTTPException(status_code=400, detail="Cannot claim account from shadow user")
    
    # 查找对应的影子用户
    shadow_user = UserService.find_shadow_user(
        external_user_id=claim_request.external_user_id,
        service_name=claim_request.service_name
    )
    
    if not shadow_user:
        raise HTTPException(status_code=404, detail="No shadow account found")
    
    # 执行数据迁移
    UserService.merge_shadow_user_to_real_user(shadow_user.id, current_user.id)
    
    # 更新服务映射
    ServiceUserMappingService.update_mapping(
        service_api_key=claim_request.service_name,
        external_user_id=claim_request.external_user_id,
        new_internal_user_id=current_user.id
    )
    
    return {"message": "Account claimed successfully", "migrated_tasks": True}

@router.get("/check-shadow-account/{external_user_id}/{service_name}")
async def check_shadow_account(request: Request, external_user_id: str, service_name: str):
    """检查是否有可迁移的影子账户"""
    if not hasattr(request.state, 'user') or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = request.state.user
    
    shadow_user = UserService.find_shadow_user(external_user_id, service_name)
    
    if not shadow_user:
        return MigrationStatusResponse(has_shadow_account=False)
    
    task_count = len(TaskService.get_tasks_by_user(shadow_user.id))
    
    return MigrationStatusResponse(
        has_shadow_account=True,
        shadow_user_id=shadow_user.id,
        task_count=task_count,
        can_migrate=True
    )
