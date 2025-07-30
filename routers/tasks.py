import io
from pathlib import Path
import json
from typing import List
import zipfile
import asyncio
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from database.services import TaskService
from responses.basic_response import DockResponse, MoleculeResponse, TaskResponse
from config import ROOT
from config.api_config import CACHE_SETTINGS, TASK_STATUS_PRIORITY
from utils.log import get_logger
from starlette.responses import FileResponse

logger = get_logger("tasks_router", str(ROOT / "logs" / "tasks.log"), isMain=True)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

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
    
@router.get("/", response_model=List[TaskResponse], 
           summary="高优先级任务列表查询",
           description="获取用户任务列表，使用缓存优化，减少阻塞")
async def list_user_tasks(request: Request):
    """
    列出当前登录用户提交的所有任务。
    使用缓存机制，提供高优先级响应，减少AutoDock运行时的阻塞。
    """
    current_user = request.state.user
    logger.info("User %s listing tasks (high priority)", current_user.username)
    
    # 使用缓存机制快速响应
    try:
        tasks = await _get_cached_tasks(current_user.id)
        return tasks
    except Exception as e:
        logger.error("Failed to get cached tasks for user %s: %s", current_user.username, e)
        # 降级到直接数据库查询
        tasks = TaskService.get_tasks_by_user(current_user.id)
        return tasks

@router.get("/{task_id}", response_model=TaskResponse,
           summary="高优先级任务状态查询", 
           description="快速获取任务状态，优化响应速度")
async def get_task_status(request: Request, task_id: str):
    """
    获取指定任务的状态和详细信息。
    使用优化查询，减少AutoDock运行时的阻塞。
    """
    current_user = request.state.user
    logger.info("User %s requesting status for task %s (high priority)", current_user.username, task_id)
    
    # 异步执行数据库查询，避免阻塞
    try:
        task = await asyncio.get_event_loop().run_in_executor(
            None, TaskService.get_task, task_id
        )
        
        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="task not found")
        
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching task %s for user %s: %s", 
                    task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")


@router.get("/{task_id}/status",
           summary="超快速任务状态检查",
           description="最小化响应时间的状态检查接口")
async def get_task_status_simple(request: Request, task_id: str):
    """
    获取任务状态的简化版本，用于前端轮询检查。
    专门优化为最快响应速度。
    返回格式: {"status": "pending|processing|finished|failed", "progress": number, "poll_interval": number}
    """
    current_user = request.state.user
    
    # 使用异步执行，提高响应速度
    try:
        task = await asyncio.get_event_loop().run_in_executor(
            None, TaskService.get_task, task_id
        )
        
        if not task or task.user_id != current_user.id:
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
            "updated_at": task.updated_at,
            "poll_interval": poll_interval,
            "can_download": task.status == "finished"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching task status %s for user %s: %s", 
                    task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")

@router.get("/{task_id}/download")
async def download_task_files(request: Request, task_id: str):
    """Download result files of a finished task as a zip archive."""
    current_user = request.state.user
    task = TaskService.get_task(task_id)
    
    if not task or task.user_id != current_user.id:
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

    logger.info("User %s downloading files for task %s", current_user.username, task_id)

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
    current_user = request.state.user
    task = TaskService.get_task(task_id)

    if not task or task.user_id != current_user.id:
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

    logger.info("User %s requesting generated molecules for task %s", current_user.username, task_id)
    
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
    current_user = request.state.user
    task = TaskService.get_task(task_id)

    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="task type is not docking")
    
    # 优化状态检查
    if task.status == "pending":
        raise HTTPException(status_code=425, detail="task is pending")
    elif task.status == "processing":
        raise HTTPException(status_code=202, detail="task is still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=410, detail="task failed")
    elif task.status != "finished":
        raise HTTPException(status_code=409, detail=f"task status is {task.status}")

    logger.info("User %s requesting docking results for task %s", current_user.username, task_id)

    output_path = Path(task.job_dir) / "dockRes.json"
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
    current_user = request.state.user
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
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
    logger.info("User %s downloading SDF file %s for task %s", current_user.username, filename, task_id)
    
    # 验证文件名格式，防止路径遍历攻击
    if not filename.endswith('.sdf') or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    
    # 构建SDF文件路径
    sdf_path = Path(task.job_dir) / "docked" / filename
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
    current_user = request.state.user
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
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
    logger.info("User %s downloading protein file for task %s", current_user.username, task_id)
    
    # 从dockRes.json中获取protein路径
    dock_res_path = Path(task.job_dir) / "dockRes.json"
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
    获取肽段优化任务的结果CSV文件
    """
    current_user = request.state.user
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
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
    logger.info("User %s downloading peptide result CSV for task %s", current_user.username, task_id)
    
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
    current_user = request.state.user
    task = TaskService.get_task(task_id)
    
    if not task or task.user_id != current_user.id:
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

    logger.info("User %s downloading peptide output folder for task %s", current_user.username, task_id)

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
