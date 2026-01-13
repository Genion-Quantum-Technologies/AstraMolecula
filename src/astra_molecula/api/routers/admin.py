import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from astra_molecula.db.services.user_service import UserService
from astra_molecula.db.services.task_service import TaskService
from astra_molecula.db.models.user import User
from astra_molecula.core.security.auth import get_admin_user
from astra_molecula.schemas.responses.basic_response import TaskResponse

logger = logging.getLogger("admin_router")
router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/users", summary="管理员获取所有用户列表")
async def list_all_users(
    current_user: User = Depends(get_admin_user),
    limit: int = Query(100, description="返回用户数量限制", ge=1, le=1000)
) -> List[Dict[str, Any]]:
    """
    管理员接口：获取所有用户列表，包括通过API key创建的影子用户
    
    返回用户信息包括：
    - 基本信息：ID、用户名、邮箱、电话
    - 创建信息：创建时间、更新时间
    - 用户类型：是否为影子用户、来源系统
    - 权限信息：角色、是否为管理员
    """
    logger.info("Admin %s requesting user list (limit: %d)", current_user.username, limit)
    
    try:
        users = UserService.list_users(limit)
        
        # 构建返回数据，排除敏感信息
        user_list = []
        for user in users:
            user_info = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "is_shadow_user": user.is_shadow_user,
                "source_system": user.source_system,
                "external_user_id": user.external_user_id,
                "created_by_service": user.created_by_service,
                "user_role": user.user_role,
                "is_admin": user.is_admin,
                "migrated_to": user.migrated_to
            }
            user_list.append(user_info)
        
        logger.info("Admin %s retrieved %d users", current_user.username, len(user_list))
        return user_list
    
    except Exception as e:
        logger.error("Error retrieving user list for admin %s: %s", current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve user list")

@router.get("/tasks", summary="管理员获取所有任务列表")
async def list_all_tasks(
    current_user: User = Depends(get_admin_user),
    limit: int = Query(100, description="返回任务数量限制", ge=1, le=1000),
    user_id: str = Query(None, description="筛选特定用户的任务"),
    task_type: str = Query(None, description="筛选特定类型的任务"),
    status: str = Query(None, description="筛选特定状态的任务")
) -> List[Dict[str, Any]]:
    """
    管理员接口：获取所有用户的所有任务列表
    
    支持筛选条件：
    - user_id: 特定用户的任务
    - task_type: 特定类型的任务 (generate, docking等)
    - status: 特定状态的任务 (pending, running, finished等)
    
    返回任务信息包括：
    - 任务基本信息：ID、类型、状态、进度
    - 用户信息：用户ID、用户名
    - 时间信息：创建时间、开始时间、完成时间
    """
    logger.info("Admin %s requesting task list (limit: %d, filters: user_id=%s, type=%s, status=%s)", 
                current_user.username, limit, user_id, task_type, status)
    
    try:
        # 获取所有任务
        tasks = TaskService.get_all_tasks_for_admin(
            limit=limit, 
            user_id=user_id, 
            task_type=task_type, 
            status=status
        )
        
        # 获取用户信息映射
        user_map = {}
        if tasks:
            user_ids = list(set(task.user_id for task in tasks))
            for uid in user_ids:
                user = UserService.get_user_by_id(uid)
                if user:
                    user_map[uid] = {
                        "username": user.username,
                        "email": user.email,
                        "is_shadow_user": user.is_shadow_user,
                        "source_system": user.source_system
                    }
        
        # 构建返回数据
        task_list = []
        for task in tasks:
            user_info = user_map.get(task.user_id, {
                "username": "Unknown",
                "email": None,
                "is_shadow_user": False,
                "source_system": "unknown"
            })
            
            task_info = {
                "id": task.id,
                "user_id": task.user_id,
                "username": user_info["username"],
                "user_email": user_info["email"],
                "user_type": "Shadow User" if user_info["is_shadow_user"] else "Regular User",
                "source_system": user_info["source_system"],
                "task_type": task.task_type,
                "status": task.status,
                "job_dir": task.job_dir,
                "created_at": task.created_at,
                "started_at": task.started_at,
                "finished_at": task.finished_at,
                "updated_at": task.updated_at,
                "progress_info": getattr(task, 'progress_info', None)
            }
            task_list.append(task_info)
        
        logger.info("Admin %s retrieved %d tasks", current_user.username, len(task_list))
        return task_list
    
    except Exception as e:
        logger.error("Error retrieving task list for admin %s: %s", current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to retrieve task list")

@router.get("/statistics", summary="管理员获取系统统计信息")
async def get_system_statistics(
    current_user: User = Depends(get_admin_user)
) -> Dict[str, Any]:
    """
    管理员接口：获取系统统计信息
    """
    logger.info("Admin %s requesting system statistics", current_user.username)
    
    try:
        # 获取用户统计
        all_users = UserService.list_users(limit=10000)
        regular_users = [u for u in all_users if not u.is_shadow_user]
        shadow_users = [u for u in all_users if u.is_shadow_user]
        admin_users = [u for u in all_users if u.is_admin]
        
        # 获取任务统计
        all_tasks = TaskService.get_all_tasks_for_admin(limit=10000)
        task_by_status = {}
        task_by_type = {}
        
        for task in all_tasks:
            # 按状态统计
            status = task.status
            task_by_status[status] = task_by_status.get(status, 0) + 1
            
            # 按类型统计
            task_type = task.task_type
            task_by_type[task_type] = task_by_type.get(task_type, 0) + 1
        
        statistics = {
            "users": {
                "total": len(all_users),
                "regular_users": len(regular_users),
                "shadow_users": len(shadow_users),
                "admin_users": len(admin_users)
            },
            "tasks": {
                "total": len(all_tasks),
                "by_status": task_by_status,
                "by_type": task_by_type
            }
        }
        
        logger.info("System statistics generated for admin %s", current_user.username)
        return statistics
    
    except Exception as e:
        logger.error("Error generating statistics for admin %s: %s", current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to generate statistics")