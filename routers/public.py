"""
公开访问路由 - 无需认证
用于第三方用户访问共享的肽优化结果3D结构
"""
import os
import re
import mimetypes
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from database.services import TaskService
from utils.log import get_logger
from config import ROOT

logger = get_logger("public_router", str(ROOT / "logs" / "public_access.log"), isMain=True)

router = APIRouter(prefix="/public", tags=["Public Access"])


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
    # 只允许字母、数字、下划线、连字符和点，防止路径遍历攻击
    if not re.match(r'^[\w\-.]+$', filename):
        logger.warning(f"Invalid filename format: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename format")
    
    # 2. 只允许 PDB 文件
    if not filename.endswith('.pdb'):
        logger.warning(f"Only PDB files are allowed for public access: {filename}")
        raise HTTPException(status_code=400, detail="Only PDB files are allowed")
    
    # 3. 验证任务是否存在（不检查用户权限，因为是公开访问）
    task = TaskService.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 4. 验证任务类型
    if task.task_type != "peptide_optimization":
        logger.warning(f"Invalid task type for public peptide access: {task.task_type}")
        raise HTTPException(status_code=400, detail="Not a peptide optimization task")
    
    # 5. 获取任务目录
    job_dir = task.job_dir
    if not job_dir:
        logger.error(f"Task job_dir is missing: {task_id}")
        raise HTTPException(status_code=500, detail="Task directory not found")
    
    # 6. 搜索文件（仅在安全的输出目录中）
    search_paths = [
        os.path.join(job_dir, "output", filename),
        os.path.join(job_dir, "output", "complexes", filename),
        os.path.join(job_dir, "output", "complex", filename),
        os.path.join(job_dir, "output", "pdb", filename),
        os.path.join(job_dir, "output", "pdbs", filename),
    ]
    
    found_file = None
    for path in search_paths:
        if os.path.exists(path) and os.path.isfile(path):
            # 额外验证：确保文件路径在任务目录内（防止符号链接攻击）
            real_path = os.path.realpath(path)
            real_job_dir = os.path.realpath(job_dir)
            if real_path.startswith(real_job_dir):
                found_file = path
                logger.info(f"File found: {path}")
                break
    
    # 7. 递归搜索 output 目录（限制深度为2）
    if not found_file:
        output_dir = os.path.join(job_dir, "output")
        if os.path.isdir(output_dir):
            for root, dirs, files in os.walk(output_dir):
                # 限制搜索深度
                rel_depth = Path(root).relative_to(output_dir).parts
                if len(rel_depth) > 2:
                    continue
                
                if filename in files:
                    file_path = os.path.join(root, filename)
                    # 验证路径安全性
                    real_path = os.path.realpath(file_path)
                    real_job_dir = os.path.realpath(job_dir)
                    if real_path.startswith(real_job_dir):
                        found_file = file_path
                        logger.info(f"File found in subdirectory: {file_path}")
                        break
    
    # 8. 文件未找到
    if not found_file:
        logger.warning(f"File not found: {filename} in task {task_id}")
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    
    # 9. 返回文件内容
    try:
        # 读取文件内容并返回为纯文本
        with open(found_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Successfully served public file: {filename} (size: {len(content)} bytes)")
        
        # 返回为纯文本，便于前端 JavaScript 处理
        return PlainTextResponse(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "public, max-age=3600",  # 缓存1小时
                "Access-Control-Allow-Origin": "*",  # 允许跨域访问
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
    
    # 5. 获取任务目录
    job_dir = task.job_dir
    if not job_dir:
        logger.error(f"Task job_dir is missing: {task_id}")
        raise HTTPException(status_code=500, detail="Task directory not found")
    
    # 6. 搜索文件（仅在安全的输出目录中）
    search_paths = [
        os.path.join(job_dir, "output", filename),
        os.path.join(job_dir, "output", "sdf", filename),
        os.path.join(job_dir, "output", "ligands", filename),
    ]
    
    found_file = None
    for path in search_paths:
        if os.path.exists(path) and os.path.isfile(path):
            # 验证路径安全性
            real_path = os.path.realpath(path)
            real_job_dir = os.path.realpath(job_dir)
            if real_path.startswith(real_job_dir):
                found_file = path
                logger.info(f"File found: {path}")
                break
    
    # 7. 递归搜索 output 目录（限制深度为2）
    if not found_file:
        output_dir = os.path.join(job_dir, "output")
        if os.path.isdir(output_dir):
            for root, dirs, files in os.walk(output_dir):
                rel_depth = Path(root).relative_to(output_dir).parts
                if len(rel_depth) > 2:
                    continue
                
                if filename in files:
                    file_path = os.path.join(root, filename)
                    real_path = os.path.realpath(file_path)
                    real_job_dir = os.path.realpath(job_dir)
                    if real_path.startswith(real_job_dir):
                        found_file = file_path
                        logger.info(f"File found in subdirectory: {file_path}")
                        break
    
    # 8. 文件未找到
    if not found_file:
        logger.warning(f"File not found: {filename} in task {task_id}")
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    
    # 9. 返回文件内容
    try:
        with open(found_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Successfully served public file: {filename} (size: {len(content)} bytes)")
        
        return PlainTextResponse(
            content=content,
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
    
    # 3. 获取任务目录
    job_dir = task.job_dir
    if not job_dir:
        logger.error(f"Task job_dir is missing: {task_id}")
        raise HTTPException(status_code=500, detail="Task directory not found")
    
    found_file = None
    
    # 4. 优先从input.json读取receptor_pdbqt路径
    input_json_path = os.path.join(job_dir, "input", "input.json")
    if os.path.exists(input_json_path):
        try:
            import json
            with open(input_json_path, 'r') as f:
                input_data = json.load(f)
                receptor_path = input_data.get('receptor_pdbqt')
                if receptor_path and os.path.exists(receptor_path) and os.path.isfile(receptor_path):
                    # 验证文件类型
                    if receptor_path.endswith('.pdb') or receptor_path.endswith('.pdbqt'):
                        found_file = receptor_path
                        logger.info(f"Protein file found from input.json: {receptor_path}")
        except Exception as e:
            logger.warning(f"Failed to read receptor from input.json: {e}")
    
    # 5. 如果input.json中没有，搜索蛋白质文件（常见名称）
    if not found_file:
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
                os.path.join(job_dir, filename),
                os.path.join(job_dir, "output", filename),
                os.path.join(job_dir, "input", filename),
                os.path.join(job_dir, "receptor", filename),
            ])
        
        for path in search_paths:
            if os.path.exists(path) and os.path.isfile(path):
                # 验证路径安全性
                real_path = os.path.realpath(path)
                real_job_dir = os.path.realpath(job_dir)
                if real_path.startswith(real_job_dir):
                    found_file = path
                    logger.info(f"Protein file found in job_dir: {path}")
                    break
    
    # 6. 递归搜索（限制深度为2）
    if not found_file:
        for root, dirs, files in os.walk(job_dir):
            rel_depth = Path(root).relative_to(job_dir).parts
            if len(rel_depth) > 2:
                continue
            
            protein_filenames = [
                "receptor.pdb",
                "receptor.pdbqt",
                "protein.pdb",
                "protein.pdbqt",
                "receptorH.pdb",
                "receptorH.pdbqt",
            ]
            
            for filename in protein_filenames:
                if filename in files:
                    file_path = os.path.join(root, filename)
                    real_path = os.path.realpath(file_path)
                    real_job_dir = os.path.realpath(job_dir)
                    if real_path.startswith(real_job_dir):
                        found_file = file_path
                        logger.info(f"Protein file found in subdirectory: {file_path}")
                        break
            
            if found_file:
                break
    
    # 7. 文件未找到
    if not found_file:
        logger.warning(f"Protein file not found in task {task_id}")
        raise HTTPException(status_code=404, detail="Protein file not found")
    
    # 7. 验证文件类型
    if not (found_file.endswith('.pdb') or found_file.endswith('.pdbqt')):
        logger.warning(f"Invalid protein file type: {found_file}")
        raise HTTPException(status_code=400, detail="Only PDB/PDBQT files are allowed")
    
    # 8. 返回文件内容
    try:
        with open(found_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"Successfully served public protein file: {found_file} (size: {len(content)} bytes)")
        
        return PlainTextResponse(
            content=content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f'inline; filename="protein.pdb"',
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
            }
        )
    
    except Exception as e:
        logger.error(f"Error reading protein file {found_file}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read protein file")

