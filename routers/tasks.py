import io
from pathlib import Path
import json
from typing import List, Dict, Any, Optional
import zipfile
import asyncio
import pandas as pd
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from database.services import TaskService
from database.services.docking_task_params_service import DockingTaskParamsService
from database.services.peptide_task_params_service import PeptideTaskParamsService
from responses.basic_response import DockResponse, MoleculeResponse, TaskResponse, PaginatedTasksResponse
from config import ROOT
from config.api_config import CACHE_SETTINGS, TASK_STATUS_PRIORITY
from utils.log import get_logger
from starlette.responses import FileResponse

logger = get_logger("tasks_router", str(ROOT / "logs" / "tasks.log"), isMain=True)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

def get_current_user_info(request: Request) -> Dict[str, Any]:
    """获取当前用户信息，支持多种认证方式"""
    if not hasattr(request.state, 'user') or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    user = request.state.user
    auth_type = getattr(request.state, 'auth_type', 'user')
    external_user_id = getattr(request.state, 'external_user_id', None)
    
    return {
        'user': user,
        'auth_type': auth_type,
        'external_user_id': external_user_id,
        'is_shadow_user': getattr(user, 'is_shadow_user', False)
    }

# 创建高优先级的任务查询缓存
_task_cache = {}
_cache_lock = asyncio.Lock()

async def _get_cached_tasks(user_id: str, max_age: int = 5):
    """获取缓存的任务列表，减少数据库查询频率"""
    import time
    async with _cache_lock:
        cache_key = f"user_{user_id}_tasks"
        current_time = time.time()
        
        # 检查缓存是否有效
        if cache_key in _task_cache:
            cached_data, timestamp = _task_cache[cache_key]
            if current_time - timestamp < max_age:  # 缓存5秒内有效
                return cached_data
        
        # 缓存失效，重新获取
        tasks = TaskService.get_tasks_by_user(user_id)
        _task_cache[cache_key] = (tasks, current_time)
        
        # 清理过期缓存
        keys_to_remove = []
        for key, (_, ts) in _task_cache.items():
            if current_time - ts > 60:  # 清理1分钟前的缓存
                keys_to_remove.append(key)
        for key in keys_to_remove:
            del _task_cache[key]
            
        return tasks
    
@router.get("/", response_model=PaginatedTasksResponse,
           summary="高优先级任务列表查询",
           description="获取用户任务列表，使用缓存优化，减少阻塞，支持分页")
async def list_user_tasks(
    request: Request, 
    page: int = 1, 
    page_size: int = 20,
    task_type: Optional[str] = None,
    status: Optional[str] = None
):
    """
    列出当前用户的所有任务。
    支持用户认证和服务认证，使用缓存机制提供高优先级响应，支持分页和过滤。
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    logger.info("User %s (%s) listing tasks (page: %d, page_size: %d, type: %s, status: %s)", 
                user.username, user_info['auth_type'], page, page_size, task_type, status)
    
    # 参数验证
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:  # 限制最大页面大小
        page_size = 20
    
    try:
        # 使用带成本信息的任务查询，支持分页和过滤
        result = TaskService.get_tasks_with_cost_info(
            user.id, page=page, page_size=page_size, 
            task_type=task_type, status=status
        )
        
        # 为 peptide_optimization 任务补充 protein_path 字段
        for t in result['tasks']:
            try:
                if t.get('task_type') == 'peptide_optimization' and t.get('job_dir'):
                    candidate = Path(t['job_dir']) / 'input' / '5ffg.pdb'
                    if candidate.exists():
                        t['protein_path'] = str(candidate)
            except Exception:
                continue
        
        # 将字典转换为TaskResponse对象
        task_responses = [
            TaskResponse(
                id=task['id'],
                user_id=task['user_id'],
                task_type=task['task_type'],
                job_dir=task['job_dir'],
                status=task['status'],
                created_at=task['created_at'],
                finished_at=task['finished_at'],
                total_compute_units=task.get('total_compute_units')
            )
            for task in result['tasks']
        ]
        
        return PaginatedTasksResponse(
            tasks=task_responses,
            total=result['total'],
            page=result['page'],
            page_size=result['page_size'],
            total_pages=result['total_pages']
        )
        
    except Exception as e:
        logger.error("Failed to get paginated tasks for user %s: %s", user.username, e)
        # 降级到简单分页
        all_tasks = TaskService.get_tasks_by_user(user.id)
        
        # 简单过滤
        if task_type:
            all_tasks = [t for t in all_tasks if t.task_type == task_type]
        if status:
            all_tasks = [t for t in all_tasks if t.status == status]
            
        total = len(all_tasks)
        total_pages = (total + page_size - 1) // page_size
        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, total)
        page_tasks = all_tasks[start_idx:end_idx]
        
        # 转换为TaskResponse对象
        task_responses = [
            TaskResponse(
                id=task.id,
                user_id=task.user_id,
                task_type=task.task_type,
                job_dir=task.job_dir,
                status=task.status,
                created_at=task.created_at,
                finished_at=task.finished_at,
                total_compute_units=None
            )
            for task in page_tasks
        ]
        
        return PaginatedTasksResponse(
            tasks=task_responses,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

# ==================== CSV下载路由（必须在/{task_id}之前定义） ====================

@router.get("/{task_id}/peptide/optimization/csv")
async def download_peptide_optimization_csv(request: Request, task_id: str):
    """
    下载肽序列优化任务结果的CSV文件（用于前端组装数据的替代）
    
    为前端PeptideOptimizationTaskDetail组件提供CSV下载功能
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.task_type != "peptide_optimization":
        raise HTTPException(status_code=400, detail="Task type is not peptide_optimization")
        
    if task.status != "finished":
        raise HTTPException(status_code=409, detail=f"Task status is {task.status}, cannot download results")
    
    logger.info("User %s (%s) downloading peptide optimization CSV for task %s", 
                user.username, user_info['auth_type'], task_id)
    
    try:
        # 尝试从result.json获取详细结果
        result_json_path = Path(task.job_dir) / "output" / "result.json"
        if result_json_path.exists():
            result_data = json.loads(result_json_path.read_text(encoding="utf-8"))
            
            if 'results' in result_data:
                results = result_data['results']
                
                # 生成CSV内容 - 对应PeptideOptimizationTaskDetail的详细格式
                csv_lines = [
                    '排名,原始序列,原始序列亲和力评分,原始序列总体评分,最优序列,总体评分,分子量,等电点,芳香性,不稳定指数,疏水性,亲水性,二级结构分数'
                ]
                
                for index, result in enumerate(results, 1):
                    original_seq = result.get('originalSequence', '').replace('"', '""')
                    optimal_seq = result.get('optimalSequence', '').replace('"', '""')
                    secondary_structure = str(result.get('secondaryStructureFraction', '')).replace('"', '""')
                    
                    line = (
                        f'{index},'
                        f'"{original_seq}",'
                        f'{result.get("originalSequenceAffinityScore", "")},'
                        f'{result.get("originalSequenceGlobalScore", "")},'
                        f'"{optimal_seq}",'
                        f'{result.get("globalScore", "")},'
                        f'{result.get("molecularWeight", "")},'
                        f'{result.get("isoelectricPoint", "")},'
                        f'{result.get("aromaticity", "")},'
                        f'{result.get("instabilityIndex", "")},'
                        f'{result.get("hydrophobicity", "")},'
                        f'{result.get("hydrophilicity", "")},'
                        f'"{secondary_structure}"'
                    )
                    csv_lines.append(line)
                
                csv_content = '\n'.join(csv_lines)
                
                return StreamingResponse(
                    io.BytesIO(csv_content.encode('utf-8-sig')),  # 使用UTF-8 BOM编码支持中文
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename=peptide_optimization_results_{task_id}.csv",
                        "Cache-Control": "no-cache"
                    }
                )
        
        # 如果没有找到result.json，尝试使用现有的result.csv文件
        result_csv_path = Path(task.job_dir) / "output" / "result.csv"
        if result_csv_path.exists():
            return FileResponse(
                path=str(result_csv_path),
                media_type="text/csv",
                filename=f"peptide_optimization_results_{task_id}.csv",
                headers={"Cache-Control": "no-cache"}
            )
        
        raise HTTPException(status_code=404, detail="No peptide optimization results found")
        
    except Exception as e:
        logger.error("Error generating peptide optimization CSV for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")

@router.get("/{task_id}/peptide/results/csv")
async def download_peptide_results_csv(request: Request, task_id: str):
    """
    下载肽序列优化结果的CSV文件（简化版本）
    
    为前端PeptideOptimization组件的主页面结果下载提供支持
    对应动态列结构的结果数据
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.task_type != "peptide_optimization":
        raise HTTPException(status_code=400, detail="Task type is not peptide_optimization")
        
    if task.status != "finished":
        raise HTTPException(status_code=409, detail=f"Task status is {task.status}, cannot download results")
    
    logger.info("User %s (%s) downloading peptide results CSV for task %s", 
                user.username, user_info['auth_type'], task_id)
    
    try:
        # 尝试使用现有的result.csv文件（这是最常见的情况）
        result_csv_path = Path(task.job_dir) / "output" / "result.csv"
        if result_csv_path.exists():
            return FileResponse(
                path=str(result_csv_path),
                media_type="text/csv",
                filename=f"peptide_results_{task_id}.csv",
                headers={"Cache-Control": "no-cache"}
            )
        
        raise HTTPException(status_code=404, detail="No peptide results found")
        
    except Exception as e:
        logger.error("Error downloading peptide results CSV for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Error downloading CSV: {str(e)}")

@router.get("/{task_id}", response_model=TaskResponse,
           summary="高优先级任务状态查询", 
           description="快速获取任务状态，优化响应速度")
async def get_task_status(request: Request, task_id: str):
    """
    获取指定任务的状态和详细信息。
    支持用户认证和服务认证，使用优化查询减少阻塞。
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    logger.info("User %s (%s) requesting status for task %s (high priority)", 
                user.username, user_info['auth_type'], task_id)
    
    # 异步执行数据库查询，避免阻塞
    try:
        task = await asyncio.get_event_loop().run_in_executor(
            None, TaskService.get_task, task_id
        )
        
        if not task or task.user_id != user.id:
            raise HTTPException(status_code=404, detail="task not found")
        # 个别任务（peptide_optimization）补充 protein_path
        try:
            if getattr(task, 'task_type', None) == 'peptide_optimization' and getattr(task, 'job_dir', None):
                candidate = Path(task.job_dir) / 'input' / '5ffg.pdb'
                if candidate.exists():
                    setattr(task, 'protein_path', str(candidate))
        except Exception:
            pass
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching task %s for user %s (%s): %s", 
                    task_id, user.username, user_info['auth_type'], e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")

@router.get("/{task_id}/peptide/protein", summary="获取多肽优化任务受体蛋白文件")
async def get_peptide_protein_file(request: Request, task_id: str):
    """返回 peptide_optimization 任务复制进入 input/ 的受体 PDB 文件 (5ffg.pdb)。
    前端可用此端点在多肽优化 3D 查看中加载 cartoon 模式。
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != 'peptide_optimization':
        raise HTTPException(status_code=400, detail="task type mismatch")
    candidate = Path(task.job_dir) / 'input' / '5ffg.pdb'
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="protein file not found")
    return FileResponse(path=str(candidate), filename=candidate.name, media_type='chemical/x-pdb')


@router.get("/{task_id}/status",
           summary="超快速任务状态检查",
           description="最小化响应时间的状态检查接口")
async def get_task_status_simple(request: Request, task_id: str):
    """
    获取任务状态的简化版本，用于前端轮询检查。
    专门优化为最快响应速度。
    返回格式: {"status": "pending|processing|finished|failed", "progress": number, "poll_interval": number}
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    # 使用异步执行，提高响应速度
    try:
        task = await asyncio.get_event_loop().run_in_executor(
            None, TaskService.get_task, task_id
        )
        
        if not task or task.user_id != user.id:
            raise HTTPException(status_code=404, detail="task not found")
        
        # 根据任务状态建议轮询间隔
        status_priority = TASK_STATUS_PRIORITY.get(task.status, 0)
        if status_priority == 0:  # finished 或 failed
            poll_interval = 0  # 停止轮询
        elif status_priority == 1:  # pending
            poll_interval = 10  # 10秒轮询
        else:  # processing
            poll_interval = 5   # 5秒轮询
        
        return {
            "status": task.status,
            "progress": getattr(task, 'progress', 0),
            "updated_at": getattr(task, 'updated_at', task.created_at),
            "poll_interval": poll_interval,
            "can_download": task.status == "finished"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching task status %s for user %s (%s): %s", 
                    task_id, user.username, user_info['auth_type'], e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")


@router.get("/{task_id}/cost")
async def get_task_cost_info(request: Request, task_id: str):
    """
    获取任务的详细成本信息
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    # 验证任务权限
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    
    logger.info("User %s (%s) requesting cost info for task %s", 
               user.username, user_info['auth_type'], task_id)
    
    try:
        # 根据任务类型获取成本信息
        if task.task_type == "docking":
            # 获取docking成本摘要
            cost_summary = DockingTaskParamsService.get_cost_summary(task_id)
            if not cost_summary:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "cost_info_not_found",
                        "message": "未找到任务的成本信息，可能是较早创建的任务",
                        "suggestion": "只有在新成本系统启用后创建的任务才有详细成本信息"
                    }
                )
        elif task.task_type in ["peptide_optimization", "generate"]:
            # 获取peptide成本摘要
            cost_summary = PeptideTaskParamsService.get_cost_summary(task_id)
            if not cost_summary:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "cost_info_not_found",
                        "message": "未找到任务的成本信息，可能是较早创建的任务",
                        "suggestion": "只有在新成本系统启用后创建的任务才有详细成本信息"
                    }
                )
        else:
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": "invalid_task_type",
                    "message": f"成本信息暂不支持任务类型: {task.task_type}",
                    "task_type": task.task_type,
                    "supported_types": ["docking", "peptide_optimization", "generate"]
                }
            )
        
        # 添加任务基本信息
        response_data = {
            "task_info": {
                "task_id": task_id,
                "task_type": task.task_type,
                "status": task.status,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "finished_at": task.finished_at.isoformat() if task.finished_at else None
            },
            "cost_details": cost_summary
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching cost info for task %s: %s", task_id, e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_server_error",
                "message": "获取成本信息失败",
                "details": str(e)
            }
        )


@router.get("/{task_id}/download")
async def download_task_files(request: Request, task_id: str):
    """Download result files of a finished task as a zip archive."""
    user_info = get_current_user_info(request)
    user = user_info['user']
    task = TaskService.get_task(task_id)
    
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    
    # 优化状态检查
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")

    logger.info("User %s (%s) downloading files for task %s", 
                user.username, user_info['auth_type'], task_id)

    job_dir = Path(task.job_dir)
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="job directory missing")

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w") as zf:
        for item in job_dir.iterdir():
            if item.is_file():
                zf.write(item, arcname=item.name)
    memory_file.seek(0)

    filename = f"{task_id}.zip"
    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}",
            "ETag": f'"{task_id}-archive"'
        },
    )

@router.get("/{task_id}/geneRes", response_model=List[MoleculeResponse])
async def get_generated_molecules(request: Request, task_id: str):
    """
    获取单个 generate 任务的 output.json，并以 List[MoleculeOutput] 格式返回。
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    task = TaskService.get_task(task_id)

    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "generate":
        raise HTTPException(status_code=400, detail="task type is not generate")
    
    # 优化状态检查
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")

    logger.info("User %s (%s) requesting generated molecules for task %s", 
                user.username, user_info['auth_type'], task_id)
    
    output_path = Path(task.job_dir) / "output.json"
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="output not found")

    # 读取并解析 output.json，假设它是 List[dict] 且每个 dict 都符合 MoleculeOutput 的字段
    data = json.loads(output_path.read_text(encoding="utf-8"))
    return data


@router.get("/{task_id}/dockRes", response_model=List[DockResponse])
async def get_docking_results(request: Request, task_id: str):
    """
    获取单个 docking 任务的 dockRes.json，并以 List[DockResponse] 格式返回。
    包含每个ligand的对接结果以及使用的protein路径信息。
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    task = TaskService.get_task(task_id)

    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="task type is not docking")
    
    # 优化状态检查
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        # 提供更详细的失败信息
        raise HTTPException(
            status_code=410, 
            detail={
                "message": "task failed",
                "error": "Task execution failed. Please check the input parameters and try again.",
                "task_id": task_id
            }
        )
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")

    logger.info("User %s (%s) requesting docking results for task %s", user.username, user_info['auth_type'], task_id)

    output_path = Path(task.job_dir) / "output" / "dockRes.json"
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="dockRes not found")

    # 读取并解析 output.json，假设它是 List[dict] 且每个 dict 都符合 MoleculeOutput 的字段
    data = json.loads(output_path.read_text(encoding="utf-8"))
    return data


@router.get("/{task_id}/sdf/{filename}")
async def get_sdf_file(request: Request, task_id: str, filename: str):
    """
    获取docking任务生成的SDF文件
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="task type is not docking")
    
    # 优化状态检查 - 根据不同状态返回不同的错误码
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")
    
    # 减少日志频率 - 只在成功访问时记录
    logger.info("User %s (%s) downloading SDF file %s for task %s", user.username, user_info['auth_type'], filename, task_id)
    
    # 验证文件名格式，防止路径遍历攻击
    if not filename.endswith('.sdf') or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    
    # 构建SDF文件路径
    sdf_path = Path(task.job_dir) / "output" / "docked" / filename
    if not sdf_path.exists():
        raise HTTPException(status_code=404, detail="SDF file not found")
    
    # 返回SDF文件内容，添加缓存头
    return FileResponse(
        path=str(sdf_path),
        media_type="chemical/x-mdl-sdfile",
        filename=filename,
        headers={
            "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}",
            "ETag": f'"{task_id}-{filename}"'
        }
    )


@router.get("/{task_id}/protein")
async def get_protein_file(request: Request, task_id: str):
    """
    获取docking任务使用的protein文件内容
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="task type is not docking")
    
    # 优化状态检查 - 根据不同状态返回不同的错误码
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")
    
    # 减少日志频率 - 只在成功访问时记录
    logger.info("User %s (%s) downloading protein file for task %s", user.username, user_info['auth_type'], task_id)
    
    # 从dockRes.json中获取protein路径
    dock_res_path = Path(task.job_dir) / "output" / "dockRes.json"
    if not dock_res_path.exists():
        raise HTTPException(status_code=404, detail="dockRes not found")
    
    try:
        with open(dock_res_path, 'r', encoding='utf-8') as f:
            dock_results = json.loads(f.read())
        
        if not dock_results or not isinstance(dock_results, list) or len(dock_results) == 0:
            raise HTTPException(status_code=404, detail="no docking results found")
        
        # 获取第一个结果中的protein_path
        protein_path = dock_results[0].get('protein_path')
        if not protein_path:
            raise HTTPException(status_code=404, detail="protein_path not found in results")
        
        protein_file_path = Path(protein_path)
        if not protein_file_path.exists():
            raise HTTPException(status_code=404, detail="protein file not found")
        
        # 返回protein文件内容，添加缓存头
        return FileResponse(
            path=str(protein_file_path),
            media_type="chemical/x-pdbqt",
            filename=protein_file_path.name,
            headers={
                "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}",
                "ETag": f'"{task_id}-protein"'
            }
        )
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="invalid dockRes format")
    except Exception as e:
        logger.exception("Error getting protein file: %s", e)
        raise HTTPException(status_code=500, detail=f"error getting protein file: {e}")


@router.get("/{task_id}/peptide/result")
async def get_peptide_result_csv(request: Request, task_id: str):
    """
    获取肽段优化任务的结果数据，以JSON格式返回供前端页面展示
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "peptide_optimization":
        raise HTTPException(status_code=400, detail="task type is not peptide_optimization")
    
    # 优化状态检查 - 根据不同状态返回不同的错误码
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")
    
    # 记录获取操作
    logger.info("User %s (%s) requesting peptide result data for task %s", user.username, user_info['auth_type'], task_id)
    
    # 构建result.csv文件路径
    result_csv_path = Path(task.job_dir) / "output" / "result.csv"
    if not result_csv_path.exists():
        raise HTTPException(status_code=404, detail="result.csv file not found")
    
    try:
        # 读取CSV文件并转换为JSON格式
        df = pd.read_csv(result_csv_path, index_col=0)
        
        # 转换为字典格式，保持索引作为行标识
        result_data = {
            "task_id": task_id,
            "task_status": task.status,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "finished_at": task.finished_at.isoformat() if task.finished_at else None,
            "data": {
                "columns": df.columns.tolist(),  # 列名列表
                "index": df.index.tolist(),      # 行索引列表
                "rows": []                       # 行数据
            }
        }
        
        # 逐行转换数据
        for idx, row in df.iterrows():
            row_data = {
                "index": idx,
                "values": {}
            }
            for col in df.columns:
                value = row[col]
                # 处理NaN值
                if pd.isna(value):
                    row_data["values"][col] = None
                else:
                    row_data["values"][col] = value
            result_data["data"]["rows"].append(row_data)
        
        return result_data
        
    except Exception as e:
        logger.error("Error reading CSV file for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Failed to read result file: {str(e)}")


@router.get("/{task_id}/peptide/result/download")
async def download_peptide_result_csv(request: Request, task_id: str):
    """
    下载肽段优化任务的结果CSV文件（原始文件下载）
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "peptide_optimization":
        raise HTTPException(status_code=400, detail="task type is not peptide_optimization")
    
    # 优化状态检查 - 根据不同状态返回不同的错误码
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")
    
    # 记录下载操作
    logger.info("User %s (%s) downloading peptide result CSV file for task %s", user.username, user_info['auth_type'], task_id)
    
    # 构建result.csv文件路径
    result_csv_path = Path(task.job_dir) / "output" / "result.csv"
    if not result_csv_path.exists():
        raise HTTPException(status_code=404, detail="result.csv file not found")
    
    # 返回CSV文件内容，添加缓存头
    return FileResponse(
        path=str(result_csv_path),
        media_type="text/csv",
        filename="result.csv",
        headers={
            "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}",
            "ETag": f'"{task_id}-result-csv"'
        }
    )


@router.get("/{task_id}/peptide/output")
async def download_peptide_output_folder(request: Request, task_id: str):
    """
    下载肽段优化任务的整个output文件夹，打包为ZIP压缩包
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    task = TaskService.get_task(task_id)
    
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "peptide_optimization":
        raise HTTPException(status_code=400, detail="task type is not peptide_optimization")
    
    # 优化状态检查
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")

    logger.info("User %s (%s) downloading peptide output folder for task %s", user.username, user_info['auth_type'], task_id)

    output_dir = Path(task.job_dir) / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="output directory not found")

    # 创建内存中的ZIP文件
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
        # 递归添加output目录下的所有文件
        for item in output_dir.rglob("*"):
            if item.is_file():
                # 计算相对路径，保持目录结构
                arcname = item.relative_to(output_dir)
                zf.write(item, arcname=str(arcname))
    
    memory_file.seek(0)

    filename = f"peptide_optimization_{task_id}_output.zip"
    return StreamingResponse(
        memory_file,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}",
            "ETag": f'"{task_id}-output-archive"'
        },
    )


@router.get("/{task_id}/input")
async def get_task_input_params(request: Request, task_id: str):
    """
    获取任务的输入参数，用于重新提交失败的任务
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    
    logger.info("User %s (%s) requesting input params for task %s", 
                user.username, user_info['auth_type'], task_id)
    
    # 根据任务类型查找不同的输入文件
    job_dir = Path(task.job_dir)
    
    if task.task_type == "docking":
        input_file = job_dir / "input" / "input.json"
    elif task.task_type == "generate":
        input_file = job_dir / "input.json"
    else:
        raise HTTPException(status_code=400, detail=f"unsupported task type: {task.task_type}")
    
    if not input_file.exists():
        raise HTTPException(status_code=404, detail="task input parameters not found")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            input_params = json.load(f)
        return input_params
    except Exception as e:
        logger.error("Failed to read input params for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="failed to read task input parameters")


@router.get("/{task_id}/peptide/download/{filename}")
async def download_peptide_file(request: Request, task_id: str, filename: str):
    """下载肽优化任务生成的单个结构文件 (PDB/SDF/MOL/MOL2 等)
    前端3D查看功能依赖此端点。在主服务(端口8000)上补充与 peptide_opt 子服务一致的能力，
    以便统一API_BASE_URL。
    查找顺序与 peptide_opt/main.py 中实现保持一致，尽可能提升复用体验。
    """
    import re, os, mimetypes, io, zipfile
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from pathlib import Path
    logger.info(f"[peptide-download] task_id={task_id} filename={filename}")

    # 基本校验
    if not re.match(r'^[\w\-. ]+$', filename):
        raise HTTPException(status_code=400, detail="invalid filename")

    user_info = get_current_user_info(request)
    user = user_info['user']
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "peptide_optimization":
        raise HTTPException(status_code=400, detail="task type mismatch")

    job_dir = task.job_dir
    if not job_dir:
        raise HTTPException(status_code=500, detail="task job_dir missing")

    search_paths = [
        os.path.join(job_dir, "output", filename),
        os.path.join(job_dir, "output", "complexes", filename),
        os.path.join(job_dir, "output", "complex", filename),
        os.path.join(job_dir, "output", "pdb", filename),
        os.path.join(job_dir, "output", "pdbs", filename),
        os.path.join(job_dir, "middlefiles", filename),
        os.path.join(job_dir, "middlefiles", "pdb", filename),
        os.path.join(job_dir, "input", filename),
        os.path.join(job_dir, filename),
    ]

    found_file = None
    for p in search_paths:
        if os.path.exists(p) and os.path.isfile(p):
            found_file = p
            break

    # 递归浅层扩展搜索
    if not found_file:
        for base in [os.path.join(job_dir, "output"), os.path.join(job_dir, "middlefiles")]:
            if os.path.isdir(base):
                for root, dirs, files in os.walk(base):
                    # 限制搜索深度为2
                    rel_depth = Path(root).relative_to(base).parts
                    if len(rel_depth) > 2:
                        continue
                    if filename in files:
                        found_file = os.path.join(root, filename)
                        break
                if found_file:
                    break

    if not found_file:
        raise HTTPException(status_code=404, detail=f"file {filename} not found")

    # MIME 类型
    mime_map = {
        '.pdb': 'chemical/x-pdb',
        '.sdf': 'chemical/x-mdl-sdfile',
        '.mol': 'chemical/x-mdl-molfile',
        '.mol2': 'chemical/x-mol2'
    }
    ext = os.path.splitext(filename)[1].lower()
    media_type = mime_map.get(ext) or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    return FileResponse(path=found_file, filename=filename, media_type=media_type)


# ==================== 新增的CSV下载API端点 ====================

@router.get("/{task_id}/generate/results/csv")
async def download_generate_results_csv(request: Request, task_id: str):
    """
    下载分子生成任务结果的CSV文件
    
    为前端ResultsDisplay组件提供CSV下载功能
    替代前端组装数据的方式
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.task_type != "generate":
        raise HTTPException(status_code=400, detail="Task type is not generate")
        
    if task.status != "finished":
        raise HTTPException(status_code=409, detail=f"Task status is {task.status}, cannot download results")
    
    logger.info("User %s (%s) downloading generate results CSV for task %s", 
                user.username, user_info['auth_type'], task_id)
    
    try:
        # 从文件系统获取结果数据
        output_path = Path(task.job_dir) / "output.json"
        if not output_path.exists():
            raise HTTPException(status_code=404, detail="Results file not found")
        
        # 读取output.json文件
        result_data = json.loads(output_path.read_text(encoding="utf-8"))
        
        # 生成CSV内容
        csv_lines = ['SMILE,MolWt,TPSA,SLogP,SA,QED']
        
        for mol in result_data:
            line = f"{mol.get('smile', '')},{mol.get('molwt', '')},{mol.get('tpsa', '')},{mol.get('slogp', '')},{mol.get('sa', '')},{mol.get('qed', '')}"
            csv_lines.append(line)
        
        csv_content = '\n'.join(csv_lines)
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8-sig')),  # 使用UTF-8 BOM编码支持中文
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=generated_analogs_{task_id}.csv",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        logger.error("Error generating CSV for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")


@router.get("/{task_id}/docking/results/csv")
async def download_docking_results_csv(
    request: Request, 
    task_id: str,
    indices: Optional[str] = None  # 可选的索引参数，格式如 "0,2,5"
):
    """
    下载分子对接任务结果的CSV文件
    
    为前端DockingTaskDetail组件提供CSV下载功能
    替代前端组装数据的方式
    
    参数:
        task_id: 任务ID
        indices: 可选的结果索引，用逗号分隔（如 "0,2,5"），不传则下载所有结果
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="Task type is not docking")
        
    if task.status != "finished":
        raise HTTPException(status_code=409, detail=f"Task status is {task.status}, cannot download results")
    
    logger.info("User %s (%s) downloading docking results CSV for task %s (indices: %s)", 
                user.username, user_info['auth_type'], task_id, indices or "all")
    
    try:
        # 从文件系统获取对接结果数据
        dockres_path = Path(task.job_dir) / "output" / "dockRes.json"
        if not dockres_path.exists():
            raise HTTPException(status_code=404, detail="Docking results file not found")
        
        # 读取dockRes.json文件
        docking_results = json.loads(dockres_path.read_text(encoding="utf-8"))
        
        # 如果提供了索引参数，过滤结果
        if indices:
            try:
                selected_indices = [int(i.strip()) for i in indices.split(',')]
                # 过滤出选中的结果
                filtered_results = []
                for idx in selected_indices:
                    if 0 <= idx < len(docking_results):
                        filtered_results.append(docking_results[idx])
                    else:
                        logger.warning("Index %d out of range for task %s (total results: %d)", 
                                     idx, task_id, len(docking_results))
                
                docking_results = filtered_results
                logger.info("Filtered to %d results from indices: %s", 
                           len(docking_results), indices)
            except ValueError as e:
                logger.error("Invalid indices format: %s, error: %s", indices, str(e))
                raise HTTPException(status_code=400, detail=f"Invalid indices format: {indices}")
        
        # 生成CSV内容
        csv_lines = ['Ligand名称,SMILES表达式,对接评分 (Docking Score),SDF文件名']
        
        for result in docking_results:
            title = result.get('title', '').replace('"', '""')  # 转义双引号
            smiles = result.get('smiles', '').replace('"', '""')  # 转义双引号
            score = result.get('score', 0)
            file = result.get('file', '').replace('"', '""')  # 转义双引号
            
            line = f'"{title}","{smiles}",{score:.2f},"{file}"'
            csv_lines.append(line)
        
        csv_content = '\n'.join(csv_lines)
        
        # 文件名根据是否有选中来区分
        filename = f"docking_results_{task_id}_selected.csv" if indices else f"docking_results_{task_id}.csv"
        
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8-sig')),  # 使用UTF-8 BOM编码支持中文
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating docking CSV for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")


@router.get("/{task_id}/docking/binding-analysis/csv/download")
async def download_all_binding_mode_summary_csv(request: Request, task_id: str):
    """
    下载分子对接任务中所有的binding_mode_summary.csv文件（打包为ZIP）
    
    从 binding_analysis 文件夹中获取所有的 {compound_id}_binding_mode_summary.csv 文件
    并将它们打包成一个ZIP文件返回给前端
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="Task type is not docking")
        
    if task.status != "finished":
        raise HTTPException(status_code=409, detail=f"Task status is {task.status}, cannot download results")
    
    logger.info("User %s (%s) downloading binding mode summary CSV files for task %s", 
                user.username, user_info['auth_type'], task_id)
    
    try:
        # 获取binding_analysis文件夹路径
        # binding_analysis 文件夹在 output/docked/ 下
        binding_analysis_dir = Path(task.job_dir) / "output" / "docked" / "binding_analysis"
        
        if not binding_analysis_dir.exists():
            raise HTTPException(status_code=404, detail="Binding analysis directory not found")
        
        # 查找所有的binding_mode_summary.csv文件
        # CSV文件直接在 binding_analysis/ 下 (文件名格式: {compound_id}_binding_mode_summary.csv)
        csv_files = list(binding_analysis_dir.glob("*_binding_mode_summary.csv"))
        
        if not csv_files:
            raise HTTPException(status_code=404, detail="No binding mode summary CSV files found")
        
        # 创建内存中的ZIP文件
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for csv_file in csv_files:
                # 将CSV文件添加到ZIP中，保持原始文件名
                zip_file.write(csv_file, arcname=csv_file.name)
        
        zip_buffer.seek(0)
        
        logger.info("Successfully created ZIP with %d binding mode summary CSV files for task %s", 
                    len(csv_files), task_id)
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=binding_analysis_{task_id}.zip",
                "Cache-Control": "no-cache"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating binding analysis ZIP for task %s: %s", task_id, str(e))
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creating ZIP file: {str(e)}")
