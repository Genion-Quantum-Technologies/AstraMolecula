import io
from pathlib import Path
import json
from typing import List, Dict, Any, Optional
import zipfile
import asyncio
import pandas as pd
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, RedirectResponse
from astra_molecula.db.services import TaskService
from astra_molecula.db.services.docking_task_params_service import DockingTaskParamsService
from astra_molecula.db.services.peptide_task_params_service import PeptideTaskParamsService
from astra_molecula.schemas.responses.basic_response import DockResponse, MoleculeResponse, TaskResponse, PaginatedTasksResponse
from astra_molecula.services.storage import get_storage
from astra_molecula.core.config import ROOT, api as api_config
from astra_molecula.core.config.api_config import CACHE_SETTINGS, TASK_STATUS_PRIORITY
from astra_molecula.utils.log import get_logger
from starlette.responses import FileResponse

logger = get_logger("tasks_router", str(ROOT / "logs" / "tasks.log"), isMain=True)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# 从统一配置获取前端URL
FRONTEND_BASE_URL = api_config.frontend_base_url


# ==== SeaweedFS 存储辅助函数 ====

def normalize_storage_prefix(job_dir: str) -> str:
    """
    标准化 job_dir 为存储前缀
    
    job_dir 可能的格式:
    - 本地路径: /tmp/astramolecula/jobs/{task_type}/{job_id}
    - SeaweedFS 路径: jobs/{task_type}/{job_id}
    
    返回 SeaweedFS 路径前缀
    """
    if not job_dir:
        return job_dir
    
    # 如果是本地路径格式，需要提取 jobs/ 部分
    if job_dir.startswith('/'):
        # 格式: /tmp/astramolecula/jobs/...
        parts = job_dir.split('/tmp/astramolecula/')
        if len(parts) > 1:
            return parts[1]
        
        # 退而求其次，提取 jobs/ 开始的部分
        if '/jobs/' in job_dir:
            idx = job_dir.index('/jobs/') + 1
            return job_dir[idx:]
        
        # 无法识别的格式，记录警告
        logger.warning("Cannot normalize job_dir to storage prefix: %s", job_dir)
    
    return job_dir


async def read_json_from_storage(storage_prefix: str, relative_path: str) -> dict | list:
    """
    从 SeaweedFS 读取并解析 JSON 文件
    
    Args:
        storage_prefix: 存储路径前缀（如 jobs/docking/{job_id}）
        relative_path: 相对于 storage_prefix 的文件路径
        
    Returns:
        解析后的 JSON 对象
        
    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 解析失败
    """
    storage = get_storage()
    remote_key = f"{storage_prefix}/{relative_path}".replace('//', '/')
    
    content = await storage.download_bytes(remote_key)
    return json.loads(content.decode('utf-8'))


async def get_file_download_url(storage_prefix: str, relative_path: str, expires_in: int = 3600) -> str:
    """
    获取文件的预签名下载 URL
    
    Args:
        storage_prefix: 存储路径前缀
        relative_path: 相对于 storage_prefix 的文件路径
        expires_in: URL 有效期（秒），默认 1 小时
        
    Returns:
        预签名下载 URL
    """
    storage = get_storage()
    remote_key = f"{storage_prefix}/{relative_path}".replace('//', '/')
    
    if not await storage.file_exists(remote_key):
        raise FileNotFoundError(f"File not found: {remote_key}")
    
    return await storage.get_presigned_url(remote_key, expires=expires_in)


async def download_file_content(storage_prefix: str, relative_path: str) -> bytes:
    """
    从 SeaweedFS 下载文件内容
    
    Args:
        storage_prefix: 存储路径前缀
        relative_path: 相对于 storage_prefix 的文件路径
        
    Returns:
        文件内容的字节数据
    """
    storage = get_storage()
    remote_key = f"{storage_prefix}/{relative_path}".replace('//', '/')
    return await storage.download_bytes(remote_key)


async def check_file_exists_in_storage(storage_prefix: str, relative_path: str) -> bool:
    """
    检查 SeaweedFS 中文件是否存在
    
    Args:
        storage_prefix: 存储路径前缀
        relative_path: 相对于 storage_prefix 的文件路径
        
    Returns:
        文件是否存在
    """
    storage = get_storage()
    remote_key = f"{storage_prefix}/{relative_path}".replace('//', '/')
    return await storage.file_exists(remote_key)


async def list_storage_files(storage_prefix: str, relative_path: str = "") -> List[str]:
    """
    列出 SeaweedFS 中指定路径下的文件
    
    Args:
        storage_prefix: 存储路径前缀
        relative_path: 相对于 storage_prefix 的子目录路径
        
    Returns:
        文件路径列表
    """
    storage = get_storage()
    prefix = f"{storage_prefix}/{relative_path}".replace('//', '/').rstrip('/') + '/'
    return await storage.list_files(prefix)


async def create_zip_from_storage(storage_prefix: str, relative_path: str, file_filter: callable = None) -> io.BytesIO:
    """
    从 SeaweedFS 中的文件创建 ZIP 压缩包（内存中）
    
    Args:
        storage_prefix: 存储路径前缀
        relative_path: 要打包的相对目录路径
        file_filter: 可选的文件过滤函数，接受文件名返回 bool
        
    Returns:
        内存中的 ZIP 文件 BytesIO 对象
    """
    storage = get_storage()
    prefix = f"{storage_prefix}/{relative_path}".replace('//', '/').rstrip('/') + '/'
    
    files = await storage.list_files(prefix)
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_key in files:
            # 提取文件名
            filename = file_key.split('/')[-1]
            
            # 应用过滤器
            if file_filter and not file_filter(filename):
                continue
            
            # 跳过目录
            if file_key.endswith('/'):
                continue
            
            try:
                content = await storage.download_bytes(file_key)
                # 计算相对于 prefix 的路径作为 arcname
                arcname = file_key[len(prefix):] if file_key.startswith(prefix) else filename
                zf.writestr(arcname, content)
            except Exception as e:
                logger.warning(f"Failed to add file to ZIP: {file_key}, error: {e}")
    
    zip_buffer.seek(0)
    return zip_buffer


async def get_file_from_storage_or_local(job_dir: str, relative_path: str) -> Optional[Path]:
    """
    尝试从本地临时目录或 SeaweedFS 获取文件（向后兼容）
    
    注意：此函数保留用于向后兼容，新代码应直接使用 SeaweedFS API
    
    Args:
        job_dir: 任务目录（可能是本地路径或存储前缀）
        relative_path: 相对于 job_dir 的文件路径
    
    Returns:
        本地文件路径（如果从存储下载，会先下载到临时目录）
    """
    from astra_molecula.core.config import storage as storage_config
    
    local_path = Path(job_dir) / relative_path
    
    # 优先使用本地文件
    if local_path.exists():
        return local_path
    
    # 尝试从 SeaweedFS 获取
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(job_dir)
    remote_key = f"{storage_prefix}/{relative_path}".replace('//', '/')
    
    if await storage.file_exists(remote_key):
        # 下载到本地临时目录
        temp_dir = storage_config.temp_dir / "downloads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        local_path = temp_dir / Path(relative_path).name
        await storage.download_file(remote_key, local_path)
        return local_path
    
    return None


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
    
@router.get("", response_model=PaginatedTasksResponse,
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
async def download_peptide_optimization_csv(
    request: Request, 
    task_id: str,
    indices: Optional[str] = None  # 可选的索引参数，格式如 "1,3,5"（从1开始的排名）
):
    """
    下载肽序列优化任务结果的CSV文件（用于前端组装数据的替代）
    
    为前端PeptideOptimizationTaskDetail组件提供CSV下载功能
    
    参数:
        task_id: 任务ID
        indices: 可选的结果排名索引，用逗号分隔（如 "1,3,5"，从1开始），不传则下载所有结果
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
    
    logger.info("User %s (%s) downloading peptide optimization CSV for task %s (indices: %s)", 
                user.username, user_info['auth_type'], task_id, indices or "all")
    
    try:
        # 解析选中的索引（从1开始的排名）
        selected_indices = None
        if indices:
            try:
                selected_indices = set(int(i.strip()) for i in indices.split(','))
                logger.info("Filtering peptide results to indices: %s", selected_indices)
            except ValueError as e:
                logger.error("Invalid indices format: %s, error: %s", indices, str(e))
                raise HTTPException(status_code=400, detail=f"Invalid indices format: {indices}")
        
        # 尝试从 SeaweedFS 获取 result.json 详细结果
        storage_prefix = normalize_storage_prefix(task.job_dir)
        result_data = None
        try:
            result_data = await read_json_from_storage(storage_prefix, "output/result.json")
        except FileNotFoundError:
            pass  # 文件不存在，继续尝试 result.csv
        
        if result_data and 'results' in result_data:
            results = result_data['results']
            
            # Generate CSV content with English headers
            csv_lines = ['Rank,Original Sequence,Original Sequence Affinity Score,Original Sequence Global Score,Optimal Sequence,Global Score,Molecular Weight,Isoelectric Point,Aromaticity,Instability Index,Hydrophobicity,Hydrophilicity,Secondary Structure Fraction']
            
            for index, result in enumerate(results, 1):
                # 如果指定了索引，跳过未选中的结果
                if selected_indices is not None and index not in selected_indices:
                    continue
                    
                # 确保所有字段都是字符串类型，然后转义双引号
                original_seq = str(result.get('originalSequence', '')).replace('"', '""')
                optimal_seq = str(result.get('optimalSequence', '')).replace('"', '""')
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
            
            # 文件名根据是否有选中来区分
            filename = f"peptide_optimization_results_{task_id}_selected.csv" if indices else f"peptide_optimization_results_{task_id}.csv"
            
            return StreamingResponse(
                io.BytesIO(csv_content.encode('utf-8-sig')),  # 使用UTF-8 BOM编码支持中文
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}",
                    "Cache-Control": "no-cache"
                }
            )
        
        # 如果没有找到result.json，尝试使用现有的result.csv文件
        try:
            csv_content_bytes = await download_file_content(storage_prefix, "output/result.csv")
            
            # 如果有索引过滤，需要解析CSV并过滤
            if selected_indices:
                import csv as csv_module
                reader = csv_module.reader(io.StringIO(csv_content_bytes.decode('utf-8')))
                rows = list(reader)
                
                if rows:
                    # 保留表头
                    filtered_rows = [rows[0]]
                    # 过滤数据行（跳过表头，索引从1开始对应第2行）
                    for i, row in enumerate(rows[1:], 1):
                        if i in selected_indices:
                            filtered_rows.append(row)
                    
                    # 生成CSV内容
                    output = io.StringIO()
                    writer = csv_module.writer(output)
                    writer.writerows(filtered_rows)
                    csv_content = output.getvalue()
                    
                    filename = f"peptide_optimization_results_{task_id}_selected.csv"
                    return StreamingResponse(
                        io.BytesIO(csv_content.encode('utf-8-sig')),
                        media_type="text/csv",
                        headers={
                            "Content-Disposition": f"attachment; filename={filename}",
                            "Cache-Control": "no-cache"
                        }
                    )
            
            # 没有索引过滤，从 SeaweedFS 下载文件内容并流式返回
            file_content = await download_file_content(storage_prefix, "output/result.csv")
            return StreamingResponse(
                io.BytesIO(file_content),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=peptide_results_{task_id}.csv",
                    "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}"
                }
            )
        
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="No peptide optimization results found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating peptide optimization CSV for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Error generating CSV: {str(e)}")

@router.get("/{task_id}/peptide/results/csv")
async def download_peptide_results_csv(
    request: Request, 
    task_id: str,
    indices: Optional[str] = None  # 可选的索引参数，格式如 "1,3,5"（从1开始的排名）
):
    """
    下载肽序列优化结果的CSV文件（简化版本）
    
    为前端PeptideOptimization组件的主页面结果下载提供支持
    对应动态列结构的结果数据
    
    参数:
        task_id: 任务ID
        indices: 可选的结果排名索引，用逗号分隔（如 "1,3,5"，从1开始），不传则下载所有结果
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
    
    logger.info("User %s (%s) downloading peptide results CSV for task %s (indices: %s)", 
                user.username, user_info['auth_type'], task_id, indices or "all")
    
    try:
        # 从 SeaweedFS 获取 result.csv 文件
        storage_prefix = normalize_storage_prefix(task.job_dir)
        
        try:
            csv_content_bytes = await download_file_content(storage_prefix, "output/result.csv")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="No peptide results found")
        
        # 如果有索引过滤，需要解析CSV并过滤
        if indices:
            try:
                selected_indices = set(int(i.strip()) for i in indices.split(','))
                logger.info("Filtering peptide results to indices: %s", selected_indices)
            except ValueError as e:
                logger.error("Invalid indices format: %s, error: %s", indices, str(e))
                raise HTTPException(status_code=400, detail=f"Invalid indices format: {indices}")
            
            import csv as csv_module
            reader = csv_module.reader(io.StringIO(csv_content_bytes.decode('utf-8')))
            rows = list(reader)
            
            if rows:
                # 保留表头
                filtered_rows = [rows[0]]
                # 过滤数据行（跳过表头，索引从1开始对应第2行）
                for i, row in enumerate(rows[1:], 1):
                    if i in selected_indices:
                        filtered_rows.append(row)
                
                # 生成CSV内容
                output = io.StringIO()
                writer = csv_module.writer(output)
                writer.writerows(filtered_rows)
                csv_content = output.getvalue()
                
                logger.info("Filtered to %d results from indices: %s", 
                           len(filtered_rows) - 1, indices)
                
                filename = f"peptide_results_{task_id}_selected.csv"
                return StreamingResponse(
                    io.BytesIO(csv_content.encode('utf-8-sig')),
                    media_type="text/csv",
                    headers={
                        "Content-Disposition": f"attachment; filename={filename}",
                        "Cache-Control": "no-cache"
                    }
                )
        
        # 没有索引过滤，从 SeaweedFS 下载文件内容并流式返回
        file_content = await download_file_content(storage_prefix, "output/result.csv")
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=peptide_results_{task_id}.csv",
                "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading peptide results CSV for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail=f"Error downloading CSV: {str(e)}")

@router.get("/{task_id}/docking/params",
           summary="获取对接任务参数",
           description="获取对接任务的配置参数，包括中心坐标和盒子尺寸")
async def get_docking_task_params(request: Request, task_id: str):
    """
    获取指定对接任务的配置参数。
    返回中心坐标、盒子尺寸等对接参数，用于3D可视化中显示搜索盒子。
    """
    user_info = get_current_user_info(request)
    user = user_info['user']
    
    logger.info("User %s (%s) requesting docking params for task %s", 
                user.username, user_info['auth_type'], task_id)
    
    try:
        task = TaskService.get_task(task_id)
        
        if not task or task.user_id != user.id:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.task_type != "docking":
            raise HTTPException(status_code=400, detail="Task type is not docking")
        
        # 获取对接参数
        params = DockingTaskParamsService.get_task_params(task_id)
        
        if not params:
            raise HTTPException(status_code=404, detail="Docking parameters not found")
        
        return {
            "success": True,
            "params": {
                "center_x": params.center_x,
                "center_y": params.center_y,
                "center_z": params.center_z,
                "box_size_x": params.box_size_x,
                "box_size_y": params.box_size_y,
                "box_size_z": params.box_size_z,
                "exhaustiveness": params.exhaustiveness,
                "n_poses": params.n_poses,
                "n_ligands": params.n_ligands,
                "min_ph": params.min_ph,
                "max_ph": params.max_ph,
                "n_jobs": params.n_jobs
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching docking params for task %s: %s", task_id, str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch docking parameters")

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
        # 注意：现在 job_dir 是 SeaweedFS 路径前缀，无法直接检查本地文件
        # 前端应该通过专门的 API 获取 protein 文件
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
    
    # 尝试从本地或 SeaweedFS 获取文件
    candidate = await get_file_from_storage_or_local(task.job_dir, 'input/5ffg.pdb')
    if not candidate:
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
            # ADR 0012 P2: 这个 getattr 以前恒返回字面量 0（Task 模型没有 progress 属性，
            # tasks 表也没有这一列）。现在两者都有了，且由 Argo 的步骤进度实时投影 —— 同一行
            # 代码，现在说的是真话。响应体形状没变。
            "progress": getattr(task, 'progress', 0),
            "updated_at": getattr(task, 'updated_at', task.created_at),
            "poll_interval": poll_interval,
            "can_download": task.status == "finished",
            # 新增字段（纯增量，不破坏既有消费方）。失败时这里是**失败步骤自己的报错原文**，
            # 由 Argo 的 onExit 钩子写入。在此之前，"任务为什么失败"通过任何 API 都读不出来。
            "info": getattr(task, 'info', None),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching task status %s for user %s (%s): %s",
                    task_id, user.username, user_info['auth_type'], e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")


@router.delete("/{task_id}",
               status_code=202,
               summary="取消任务",
               description="请求取消一个仍在运行的任务（ADR 0012 P2）")
async def cancel_task(request: Request, task_id: str):
    """取消任务。

    这个端点在 ADR 0012 之前**根本不存在** —— tasks 路由的 21 条路由全是 GET，
    任务一旦提交就无法停止，哪怕它正霸占着全平台唯一一张 GPU。

    实现上刻意**不直接调用 Kubernetes**：后端没有、也不应该有 k8s 凭证。它只是把意图
    写进数据库（`status='cancelling'`），由 compute-foundry operator 去 terminate 对应的
    Argo Workflow，然后回写 `cancelled`。

    这么做不只是为了职责边界，更是为了**崩溃安全**：取消意图落在数据库里，
    operator 中途重启也不会把它丢掉，重启后会幂等地把清理做完。
    """
    user_info = get_current_user_info(request)
    user = user_info['user']

    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")

    if task.status in ("finished", "failed", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "task_already_terminal",
                "message": f"任务已处于终态，无法取消：{task.status}",
                "details": {"current_status": task.status},
            },
        )

    TaskService.update_task_status(task_id, "cancelling")
    logger.info("Task %s marked cancelling by user %s", task_id, user.username)
    return {
        "task_id": task_id,
        "status": "cancelling",
        "message": "取消请求已受理，正在终止计算作业",
    }


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

    # 从 SeaweedFS 创建 ZIP 压缩包
    storage_prefix = normalize_storage_prefix(task.job_dir)
    storage = get_storage()
    
    try:
        # 列出所有输出文件
        output_files = await storage.list_files(f"{storage_prefix}/output/")
        
        if not output_files:
            raise HTTPException(status_code=404, detail="No output files found")
        
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_key in output_files:
                if file_key.endswith('/'):
                    continue
                try:
                    content = await storage.download_bytes(file_key)
                    # 提取相对路径作为 arcname
                    arcname = file_key.split('/output/')[-1] if '/output/' in file_key else file_key.split('/')[-1]
                    zf.writestr(arcname, content)
                except Exception as e:
                    logger.warning(f"Failed to add file to ZIP: {file_key}, error: {e}")
        
        memory_file.seek(0)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating ZIP for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create download archive")

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
    
    # 从 SeaweedFS 读取 output.json
    storage_prefix = normalize_storage_prefix(task.job_dir)
    try:
        data = await read_json_from_storage(storage_prefix, "output.json")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="output not found")
    
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

    # 从 SeaweedFS 读取 dockRes.json
    storage_prefix = normalize_storage_prefix(task.job_dir)
    try:
        data = await read_json_from_storage(storage_prefix, "output/dockRes.json")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="dockRes not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="dockRes format invalid")
    
    # 获取前端基础URL（优先使用环境变量配置）
    if FRONTEND_BASE_URL:
        base_url = FRONTEND_BASE_URL
    else:
        # 从请求中提取，去除端口号和 /api 路径
        base_url = f"{request.url.scheme}://{request.url.hostname}"
    
    # 为每条记录添加分享链接，并确保 title 字段是字符串
    for item in data:
        # 确保 title 字段是字符串类型（dockRes.json 中可能是整数）
        if 'title' in item and not isinstance(item['title'], str):
            item['title'] = str(item['title'])
        if 'file' in item:
            from urllib.parse import quote
            filename = quote(item['file'])
            item['share_url'] = f"{base_url}/public/docking-viewer?taskId={task_id}&filename={filename}"
    
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
    
    # 从 SeaweedFS 获取文件内容并流式返回（避免重定向到内部地址导致外网无法访问）
    storage_prefix = normalize_storage_prefix(task.job_dir)
    try:
        file_content = await download_file_content(storage_prefix, f"output/docked/{filename}")
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="chemical/x-mdl-sdfile",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="SDF file not found")


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
    
    # 从 SeaweedFS 获取 dockRes.json 来读取 protein 信息
    storage_prefix = normalize_storage_prefix(task.job_dir)
    
    try:
        dock_results = await read_json_from_storage(storage_prefix, "output/dockRes.json")
        
        if not dock_results or not isinstance(dock_results, list) or len(dock_results) == 0:
            raise HTTPException(status_code=404, detail="no docking results found")
        
        # 获取第一个结果中的 receptor_storage_key（存储在上传时的键）
        # 或者从 input.json 获取 receptor_storage_key
        storage = get_storage()
        try:
            input_config = await read_json_from_storage(storage_prefix, "input/input.json")
            receptor_storage_key = input_config.get('receptor_storage_key')
            if receptor_storage_key:
                # 从 SeaweedFS 下载文件内容并流式返回（避免重定向到内部地址导致外网无法访问）
                file_content = await storage.download_bytes(receptor_storage_key.lstrip('/'))
                return StreamingResponse(
                    io.BytesIO(file_content),
                    media_type="chemical/x-pdbqt",
                    headers={
                        "Content-Disposition": f"attachment; filename=receptor.pdbqt",
                        "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}"
                    }
                )
        except FileNotFoundError:
            pass
        
        # Fallback: 尝试从 input 目录获取 receptor 文件
        try:
            input_files = await storage.list_files(f"{storage_prefix}/input/")
            for f in input_files:
                if f.endswith('.pdbqt'):
                    file_content = await storage.download_bytes(f)
                    return StreamingResponse(
                        io.BytesIO(file_content),
                        media_type="chemical/x-pdbqt",
                        headers={
                            "Content-Disposition": f"attachment; filename={f.split('/')[-1]}",
                            "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}"
                        }
                    )
        except Exception:
            pass
        
        raise HTTPException(status_code=404, detail="protein file not found")
        
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="dockRes not found")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="invalid dockRes format")
    except HTTPException:
        raise
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
    
    # 从 SeaweedFS 读取 result.csv
    storage_prefix = normalize_storage_prefix(task.job_dir)
    try:
        csv_content = await download_file_content(storage_prefix, "output/result.csv")
        df = pd.read_csv(io.BytesIO(csv_content), index_col=0)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="result.csv file not found")
    
    try:
        
        # 获取前端基础URL（优先使用环境变量配置）
        if FRONTEND_BASE_URL:
            base_url = FRONTEND_BASE_URL
        else:
            # 从请求中提取，去除端口号和 /api 路径
            base_url = f"{request.url.scheme}://{request.url.hostname}"
        
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
        # 注意：CSV第一行是"Input peptide property"（原始序列属性），没有对应的PDB文件
        # 只有后续的"Docking result rank X"行才有对应的complex{X}.pdb文件
        for row_idx, (idx, row) in enumerate(df.iterrows()):
            row_data = {
                "index": idx,
                "values": {},
                # row_idx=0 是原始序列，没有PDB文件；row_idx>=1 对应 complex{row_idx}.pdb
                "share_url": f"{base_url}/public/peptide-viewer?taskId={task_id}&filename=complex{row_idx}.pdb" if row_idx > 0 else None
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
    
    # 从 SeaweedFS 获取文件内容并流式返回（避免重定向到内部地址导致外网无法访问）
    storage_prefix = normalize_storage_prefix(task.job_dir)
    try:
        file_content = await download_file_content(storage_prefix, "output/result.csv")
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=result_{task_id}.csv",
                "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="result.csv file not found")


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

    # 从 SeaweedFS 创建 ZIP 压缩包
    storage_prefix = normalize_storage_prefix(task.job_dir)
    try:
        zip_buffer = await create_zip_from_storage(storage_prefix, "output")
    except Exception as e:
        logger.error(f"Error creating ZIP for task {task_id}: {e}")
        raise HTTPException(status_code=404, detail="output directory not found")

    filename = f"peptide_optimization_{task_id}_output.zip"
    return StreamingResponse(
        zip_buffer,
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
    
    # 从 SeaweedFS 获取输入参数
    storage_prefix = normalize_storage_prefix(task.job_dir)
    
    if task.task_type == "docking":
        input_path = "input/input.json"
    elif task.task_type == "generate":
        input_path = "input.json"
    else:
        raise HTTPException(status_code=400, detail=f"unsupported task type: {task.task_type}")
    
    try:
        input_params = await read_json_from_storage(storage_prefix, input_path)
        return input_params
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="task input parameters not found")
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
    import re
    import mimetypes
    
    logger.info(f"[peptide-download] task_id={task_id} filename={filename}")

    # 基本校验：允许字母数字、下划线、连字符、点和空格
    if not re.match(r'^[\w\-. ]+$', filename):
        raise HTTPException(status_code=400, detail="invalid filename")

    user_info = get_current_user_info(request)
    user = user_info['user']
    task = TaskService.get_task(task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "peptide_optimization":
        raise HTTPException(status_code=400, detail="task type mismatch")

    storage_prefix = normalize_storage_prefix(task.job_dir)
    storage = get_storage()
    
    # 搜索路径（相对于 storage_prefix）
    search_paths = [
        f"output/{filename}",
        f"output/complexes/{filename}",
        f"output/complex/{filename}",
        f"output/pdb/{filename}",
        f"output/pdbs/{filename}",
        f"middlefiles/{filename}",
        f"middlefiles/pdb/{filename}",
        f"input/{filename}",
        filename,
    ]

    found_key = None
    for relative_path in search_paths:
        remote_key = f"{storage_prefix}/{relative_path}"
        if await storage.file_exists(remote_key):
            found_key = remote_key
            break

    # 递归搜索 output 和 middlefiles 目录
    if not found_key:
        for base_dir in ["output", "middlefiles"]:
            try:
                files = await storage.list_files(f"{storage_prefix}/{base_dir}/")
                for f in files:
                    if f.endswith(f"/{filename}") or f.split('/')[-1] == filename:
                        found_key = f
                        break
                if found_key:
                    break
            except Exception:
                continue

    if not found_key:
        raise HTTPException(status_code=404, detail=f"file {filename} not found")

    # 从 SeaweedFS 下载文件内容并流式返回（避免重定向到内部地址导致外网无法访问）
    import mimetypes
    try:
        file_content = await storage.download_bytes(found_key)
        mime_type, _ = mimetypes.guess_type(filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": f"public, max-age={CACHE_SETTINGS['file_cache_duration']}"
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"file {filename} not found")
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail="Failed to download file")


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
        # 从 SeaweedFS 获取结果数据
        storage_prefix = normalize_storage_prefix(task.job_dir)
        try:
            result_data = await read_json_from_storage(storage_prefix, "output.json")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Results file not found")
        
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
        # 从 SeaweedFS 获取对接结果数据
        storage_prefix = normalize_storage_prefix(task.job_dir)
        try:
            docking_results = await read_json_from_storage(storage_prefix, "output/dockRes.json")
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Docking results file not found")
        
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
        
        # Generate CSV content with English headers
        csv_lines = ['Ligand Name,SMILES,Docking Score,SDF Filename']
        
        for result in docking_results:
            # 确保所有字段都是字符串类型，然后转义双引号
            title = str(result.get('title', '')).replace('"', '""')
            smiles = str(result.get('smiles', '')).replace('"', '""')
            score = result.get('score', 0)
            file = str(result.get('file', '')).replace('"', '""')
            
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
        # 从 SeaweedFS 获取 binding_analysis 文件夹中的 CSV 文件
        storage_prefix = normalize_storage_prefix(task.job_dir)
        storage = get_storage()
        
        # 列出 binding_analysis 目录下的文件
        binding_analysis_prefix = f"{storage_prefix}/output/docked/binding_analysis/"
        all_files = await storage.list_files(binding_analysis_prefix)
        
        # 过滤出 binding_mode_summary.csv 文件
        csv_files = [f for f in all_files if f.endswith('_binding_mode_summary.csv')]
        
        if not csv_files:
            raise HTTPException(status_code=404, detail="No binding mode summary CSV files found")
        
        # 创建内存中的ZIP文件
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for csv_key in csv_files:
                try:
                    content = await storage.download_bytes(csv_key)
                    filename = csv_key.split('/')[-1]
                    zip_file.writestr(filename, content)
                except Exception as e:
                    logger.warning(f"Failed to add file to ZIP: {csv_key}, error: {e}")
        
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
