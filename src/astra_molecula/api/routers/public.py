"""
公开访问路由 - 无需认证
用于第三方用户访问共享的肽优化结果3D结构
"""
import io
import os
import re
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, StreamingResponse
from astra_molecula.db.services import TaskService
from astra_molecula.db.services.highfold_task_params_service import HighFoldTaskParamsService
from astra_molecula.services.storage import get_storage
from astra_molecula.services import highfold_results
from astra_molecula.utils.log import get_logger
from astra_molecula.core.config import ROOT

logger = get_logger("public_router", str(ROOT / "logs" / "public_access.log"), isMain=True)

router = APIRouter(prefix="/public", tags=["Public Access"])


def normalize_storage_prefix(job_dir: str) -> str:
    """
    标准化 job_dir 为存储前缀
    
    支持两种格式：
    1. 新格式（SeaweedFS 路径）: jobs/docking/{job_id}
    2. 旧格式（本地路径）: /tmp/astramolecula/jobs/docking/{job_id}
    """
    if job_dir.startswith('/'):
        parts = Path(job_dir).parts
        try:
            jobs_idx = parts.index('jobs')
            return '/'.join(parts[jobs_idx:])
        except ValueError:
            return '/'.join(parts[-3:]) if len(parts) >= 3 else job_dir
    else:
        return job_dir


@router.get("/peptide/{task_id}/complex/{filename}")
async def get_public_peptide_complex(task_id: str, filename: str):
    """
    公开访问的肽优化结果 PDB 文件
    
    允许未登录用户通过分享链接查看 3D 结构
    
    安全措施：
    - 文件名格式验证（防止路径遍历攻击）
    - 只允许访问 PDB 格式文件
    - 只在 output 目录中搜索
    
    参数：
    - task_id: 任务ID
    - filename: PDB 文件名（如 complex1.pdb）
    
    返回：
    - PDB 文件内容（text/plain）
    """
    logger.info(f"[public-peptide-access] task_id={task_id}, filename={filename}")
    
    # 1. 文件名安全验证
    if not re.match(r'^[\w\-.]+$', filename):
        logger.warning(f"Invalid filename format: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename format")
    
    # 2. 只允许 PDB 文件
    if not filename.endswith('.pdb'):
        logger.warning(f"Only PDB files are allowed for public access: {filename}")
        raise HTTPException(status_code=400, detail="Only PDB files are allowed")
    
    # 3. 验证任务是否存在
    task = TaskService.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 4. 验证任务类型
    if task.task_type != "peptide_optimization":
        logger.warning(f"Invalid task type for public peptide access: {task.task_type}")
        raise HTTPException(status_code=400, detail="Not a peptide optimization task")
    
    # 5. 从 SeaweedFS 获取文件
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    
    # 搜索路径（相对于 storage_prefix）
    search_paths = [
        f"output/{filename}",
        f"output/complexes/{filename}",
        f"output/complex/{filename}",
        f"output/pdb/{filename}",
        f"output/pdbs/{filename}",
    ]
    
    found_key = None
    for relative_path in search_paths:
        remote_key = f"{storage_prefix}/{relative_path}"
        if await storage.file_exists(remote_key):
            found_key = remote_key
            logger.info(f"File found in storage: {remote_key}")
            break
    
    # 递归搜索 output 目录
    if not found_key:
        try:
            output_files = await storage.list_files(f"{storage_prefix}/output/")
            for f in output_files:
                if f.endswith(f"/{filename}") or f.split('/')[-1] == filename:
                    found_key = f
                    logger.info(f"File found in storage subdirectory: {f}")
                    break
        except Exception as e:
            logger.warning(f"Error listing output files: {e}")
    
    if not found_key:
        logger.warning(f"File not found: {filename} in task {task_id}")
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    
    # 6. 返回文件内容
    try:
        content = await storage.download_bytes(found_key)
        logger.info(f"Successfully served public file: {filename} (size: {len(content)} bytes)")
        
        return PlainTextResponse(
            content=content.decode('utf-8'),
            media_type="text/plain",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
            }
        )
    
    except Exception as e:
        logger.error(f"Error reading file {found_file}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file")


@router.get("/peptide/{task_id}/info")
async def get_public_peptide_task_info(task_id: str):
    """
    获取肽优化任务的公开信息（基本元数据）
    
    不需要认证，用于公开分享页面显示任务信息
    
    返回：
    - task_id: 任务ID
    - task_type: 任务类型
    - status: 任务状态
    - created_at: 创建时间
    - finished_at: 完成时间（如果已完成）
    
    注意：不返回敏感信息（如 user_id, job_dir 等）
    """
    logger.info(f"[public-peptide-info] task_id={task_id}")
    
    # 获取任务信息
    task = TaskService.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 验证任务类型
    if task.task_type != "peptide_optimization":
        logger.warning(f"Invalid task type: {task.task_type}")
        raise HTTPException(status_code=400, detail="Not a peptide optimization task")
    
    # 返回公开信息（不包含敏感数据）
    public_info = {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }
    
    logger.info(f"Successfully served public task info: {task_id}")
    return public_info


@router.get("/docking/{task_id}/sdf/{filename}")
async def get_public_docking_sdf(task_id: str, filename: str):
    """
    公开访问的分子对接结果 SDF 文件
    
    允许未登录用户通过分享链接查看 3D 结构
    
    安全措施：
    - 文件名格式验证（防止路径遍历攻击）
    - 只允许访问 SDF 格式文件
    - 只在 output 目录中搜索
    
    参数：
    - task_id: 任务ID
    - filename: SDF 文件名（如 pose_1.sdf）
    
    返回：
    - SDF 文件内容（text/plain）
    """
    logger.info(f"[public-docking-access] task_id={task_id}, filename={filename}")
    
    # 1. 文件名安全验证
    if not re.match(r'^[\w\-.]+$', filename):
        logger.warning(f"Invalid filename format: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename format")
    
    # 2. 只允许 SDF 文件
    if not filename.endswith('.sdf'):
        logger.warning(f"Only SDF files are allowed for public access: {filename}")
        raise HTTPException(status_code=400, detail="Only SDF files are allowed")
    
    # 3. 验证任务是否存在
    task = TaskService.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 4. 验证任务类型
    if task.task_type != "docking":
        logger.warning(f"Invalid task type for public docking access: {task.task_type}")
        raise HTTPException(status_code=400, detail="Not a docking task")
    
    # 5. 从 SeaweedFS 获取文件
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    
    # 搜索路径（相对于 storage_prefix）
    search_paths = [
        f"output/{filename}",
        f"output/sdf/{filename}",
        f"output/ligands/{filename}",
        f"output/docked/{filename}",
    ]
    
    found_key = None
    for relative_path in search_paths:
        remote_key = f"{storage_prefix}/{relative_path}"
        if await storage.file_exists(remote_key):
            found_key = remote_key
            logger.info(f"File found in storage: {remote_key}")
            break
    
    # 递归搜索 output 目录
    if not found_key:
        try:
            output_files = await storage.list_files(f"{storage_prefix}/output/")
            for f in output_files:
                if f.endswith(f"/{filename}") or f.split('/')[-1] == filename:
                    found_key = f
                    logger.info(f"File found in storage subdirectory: {f}")
                    break
        except Exception as e:
            logger.warning(f"Error listing output files: {e}")
    
    if not found_key:
        logger.warning(f"File not found: {filename} in task {task_id}")
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    
    # 6. 返回文件内容
    try:
        content = await storage.download_bytes(found_key)
        logger.info(f"Successfully served public file: {filename} (size: {len(content)} bytes)")
        
        return PlainTextResponse(
            content=content.decode('utf-8'),
            media_type="text/plain",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
            }
        )
    
    except Exception as e:
        logger.error(f"Error reading file from storage: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file")



@router.get("/docking/{task_id}/info")
async def get_public_docking_task_info(task_id: str):
    """
    获取分子对接任务的公开信息（基本元数据）
    
    不需要认证，用于公开分享页面显示任务信息
    
    返回：
    - task_id: 任务ID
    - task_type: 任务类型
    - status: 任务状态
    - created_at: 创建时间
    - finished_at: 完成时间（如果已完成）
    
    注意：不返回敏感信息（如 user_id, job_dir 等）
    """
    logger.info(f"[public-docking-info] task_id={task_id}")
    
    task = TaskService.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.task_type != "docking":
        logger.warning(f"Invalid task type: {task.task_type}")
        raise HTTPException(status_code=400, detail="Not a docking task")
    
    public_info = {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }
    
    logger.info(f"Successfully served public docking task info: {task_id}")
    return public_info


@router.get("/docking/{task_id}/params")
async def get_public_docking_params(task_id: str):
    """
    公开访问的对接参数（用于显示 Search Box）
    
    允许未登录用户获取对接盒子参数，用于3D可视化中显示搜索区域
    
    参数：
    - task_id: 任务ID
    
    返回：
    - success: 是否成功
    - params: 对接参数
        - center_x, center_y, center_z: 对接盒子中心坐标
        - box_size_x, box_size_y, box_size_z: 对接盒子尺寸
        - exhaustiveness, n_poses 等其他参数
    """
    import json
    
    logger.info(f"[public-docking-params] task_id={task_id}")
    
    # 1. 验证任务是否存在
    task = TaskService.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 2. 验证任务类型
    if task.task_type != "docking":
        logger.warning(f"Invalid task type: {task.task_type}")
        raise HTTPException(status_code=400, detail="Not a docking task")
    
    # 3. 从 SeaweedFS 读取 input.json
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    
    try:
        remote_key = f"{storage_prefix}/input/input.json"
        content = await storage.download_bytes(remote_key)
        input_data = json.loads(content.decode('utf-8'))
        
        # 4. 提取对接盒子参数
        params = {
            "center_x": input_data.get("center_x"),
            "center_y": input_data.get("center_y"),
            "center_z": input_data.get("center_z"),
            "box_size_x": input_data.get("box_size_x"),
            "box_size_y": input_data.get("box_size_y"),
            "box_size_z": input_data.get("box_size_z"),
            "exhaustiveness": input_data.get("exhaustiveness"),
            "n_poses": input_data.get("n_poses"),
            "n_ligands": len(input_data.get("ligands", [])),
            "min_ph": input_data.get("min_ph"),
            "max_ph": input_data.get("max_ph"),
            "n_jobs": input_data.get("n_jobs"),
        }
        
        logger.info(f"Successfully served public docking params: {task_id}")
        return {
            "success": True,
            "params": params
        }
    
    except FileNotFoundError:
        logger.warning(f"input.json not found for task: {task_id}")
        raise HTTPException(status_code=404, detail="Docking parameters not found")
    except Exception as e:
        logger.error(f"Error reading input.json: {e}")
        raise HTTPException(status_code=500, detail="Failed to read docking parameters")


@router.get("/docking/{task_id}/protein")
async def get_public_docking_protein(task_id: str):
    """
    公开访问的分子对接蛋白质文件
    
    允许未登录用户通过分享链接查看蛋白质 3D 结构
    
    安全措施：
    - 只允许访问 PDB/PDBQT 格式文件
    - 只在 output 目录中搜索
    - 路径安全性验证
    
    参数：
    - task_id: 任务ID
    
    返回：
    - PDB/PDBQT 文件内容（text/plain）
    """
    import json
    
    logger.info(f"[public-docking-protein] task_id={task_id}")
    
    # 1. 验证任务是否存在
    task = TaskService.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 2. 验证任务类型
    if task.task_type != "docking":
        logger.warning(f"Invalid task type for public docking access: {task.task_type}")
        raise HTTPException(status_code=400, detail="Not a docking task")
    
    # 3. 从 SeaweedFS 获取蛋白质文件
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    
    found_key = None
    
    # 4. 优先从 input.json 读取 receptor_storage_key
    try:
        input_key = f"{storage_prefix}/input/input.json"
        content = await storage.download_bytes(input_key)
        input_data = json.loads(content.decode('utf-8'))
        receptor_storage_key = input_data.get('receptor_storage_key')
        if receptor_storage_key and await storage.file_exists(receptor_storage_key):
            found_key = receptor_storage_key
            logger.info(f"Protein file found from input.json: {receptor_storage_key}")
    except Exception as e:
        logger.warning(f"Failed to read receptor from input.json: {e}")
    
    # 5. 搜索蛋白质文件
    if not found_key:
        protein_filenames = [
            "receptor.pdb",
            "receptor.pdbqt",
            "protein.pdb",
            "protein.pdbqt",
            "receptorH.pdb",
            "receptorH.pdbqt",
        ]
        
        search_paths = []
        for filename in protein_filenames:
            search_paths.extend([
                f"{storage_prefix}/{filename}",
                f"{storage_prefix}/output/{filename}",
                f"{storage_prefix}/input/{filename}",
            ])
        
        for path in search_paths:
            if await storage.file_exists(path):
                found_key = path
                logger.info(f"Protein file found in storage: {path}")
                break
    
    # 6. 搜索 input 目录下的 .pdbqt 文件
    if not found_key:
        try:
            input_files = await storage.list_files(f"{storage_prefix}/input/")
            for f in input_files:
                if f.endswith('.pdbqt') or f.endswith('.pdb'):
                    found_key = f
                    logger.info(f"Protein file found in input directory: {f}")
                    break
        except Exception as e:
            logger.warning(f"Error listing input files: {e}")
    
    if not found_key:
        logger.warning(f"Protein file not found in task {task_id}")
        raise HTTPException(status_code=404, detail="Protein file not found")
    
    # 7. 返回文件内容
    try:
        content = await storage.download_bytes(found_key)
        logger.info(f"Successfully served public protein file: {found_key} (size: {len(content)} bytes)")
        
        return PlainTextResponse(
            content=content.decode('utf-8'),
            media_type="text/plain",
            headers={
                "Content-Disposition": f'inline; filename="protein.pdb"',
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
            }
        )
    
    except Exception as e:
        logger.error(f"Error reading protein file from storage: {e}")
        raise HTTPException(status_code=500, detail="Failed to read protein file")



# ============================================================================
# HighFold-C2C 公开访问端点
# ============================================================================
#
# 镜像 docking/peptide 模式，提供未登录可读的 HighFold-C2C 结果端点。
# 所有端点共享 highfold_results 服务模块的逻辑（与 authenticated 路由一致）。
# 安全模型：知道 task_id 即可查看；filename 走正则白名单；扩展名严格限制。
# ============================================================================


def _ensure_highfold_filename(filename: str, allowed_ext: str) -> None:
    """公开端点 filename 安全校验：正则 + 扩展名白名单。"""
    if not re.match(r'^[\w\-.]+$', filename):
        logger.warning(f"Invalid filename format: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename format")
    if not filename.endswith(allowed_ext):
        logger.warning(f"Disallowed extension for public access: {filename}")
        raise HTTPException(status_code=400, detail=f"Only {allowed_ext} files are allowed")


@router.get("/highfold/{task_id}/info")
async def get_public_highfold_task_info(task_id: str):
    """获取 HighFold-C2C 任务的公开元数据（不含 user_id 等敏感字段）"""
    logger.info(f"[public-highfold-info] task_id={task_id}")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task)
    return highfold_results.build_public_task_info(task)


@router.get("/highfold/{task_id}/params")
async def get_public_highfold_params(task_id: str):
    """获取 HighFold-C2C 任务参数（公开版本）"""
    logger.info(f"[public-highfold-params] task_id={task_id}")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task)
    params = HighFoldTaskParamsService.get_task_params(task_id)
    return {"task_id": task_id, **highfold_results.build_public_params(params)}


@router.get("/highfold/{task_id}/results")
async def get_public_highfold_results(task_id: str):
    """获取 HighFold-C2C 评估结果摘要（CSV 解析为 JSON）"""
    logger.info(f"[public-highfold-results] task_id={task_id}")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task, require_finished=True)
    return await highfold_results.fetch_results_parsed(task)


@router.get("/highfold/{task_id}/results/csv")
async def download_public_highfold_results_csv(task_id: str):
    """下载 HighFold-C2C 原始 CSV 文件"""
    logger.info(f"[public-highfold-results-csv] task_id={task_id}")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task, require_finished=True)
    content = await highfold_results.fetch_results_csv_bytes(task)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=highfold_results_{task_id[:8]}.csv",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/highfold/{task_id}/sequences")
async def get_public_highfold_sequences(task_id: str):
    """获取 HighFold-C2C 生成的 FASTA 序列"""
    logger.info(f"[public-highfold-sequences] task_id={task_id}")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task, require_finished=True)
    return await highfold_results.fetch_sequences(task)


@router.get("/highfold/{task_id}/structures")
async def list_public_highfold_structures(task_id: str):
    """列出 HighFold-C2C 输出的 PDB 结构文件"""
    logger.info(f"[public-highfold-structures] task_id={task_id}")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task, require_finished=True)
    return await highfold_results.list_structures(
        task,
        download_url_prefix=f"/public/highfold/{task_id}/structures",
    )


@router.get("/highfold/{task_id}/structures/{filename}")
async def get_public_highfold_structure(task_id: str, filename: str):
    """获取单个 PDB 结构文件的文本内容（用于 3D 查看器）"""
    logger.info(f"[public-highfold-structure] task_id={task_id}, filename={filename}")
    _ensure_highfold_filename(filename, ".pdb")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task, require_finished=True)
    content = await highfold_results.fetch_structure_pdb_bytes(task, filename)
    return PlainTextResponse(
        content=content.decode('utf-8'),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "public, max-age=3600",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/highfold/{task_id}/download")
async def download_public_highfold_all(task_id: str):
    """打包下载 HighFold-C2C 全部输出文件 (ZIP)"""
    logger.info(f"[public-highfold-download] task_id={task_id}")
    task = TaskService.get_task(task_id)
    highfold_results.ensure_highfold_task(task, require_finished=True)
    zip_bytes = await highfold_results.build_results_zip(task)
    filename = f"highfold_c2c_results_{task_id[:8]}.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )
