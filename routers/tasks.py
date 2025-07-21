import io
from pathlib import Path
import json
from typing import List
import zipfile
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from database.services import TaskService
from responses.basic_response import DockResponse, MoleculeResponse, TaskResponse
from config import ROOT
from utils.log import get_logger
from starlette.responses import FileResponse

logger = get_logger("tasks_router", str(ROOT / "logs" / "tasks.log"), isMain=True)

router = APIRouter(prefix="/tasks", tags=["Tasks"])
    
@router.get("/", response_model=List[TaskResponse])
async def list_user_tasks(request: Request):
    """
    列出当前登录用户提交的所有任务。
    """
    current_user = request.state.user
    logger.info("User %s listing tasks", current_user.username)
    tasks = TaskService.get_tasks_by_user(current_user.id)
    # 如果想在没有任务时返回 404，可以加：
    # if not tasks:
    #     raise HTTPException(status_code=404, detail="no tasks found for this user")
    return tasks

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_status(request: Request, task_id: str):
    """
    获取指定任务的状态和详细信息。
    """
    current_user = request.state.user
    logger.info("User %s requesting status for task %s", current_user.username, task_id)
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    
    return task

@router.get("/{task_id}/download")
async def download_task_files(request: Request, task_id: str):
    """Download result files of a finished task as a zip archive."""
    current_user = request.state.user
    logger.info("User %s downloading files for task %s", current_user.username, task_id)

    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "finished":
        raise HTTPException(status_code=409, detail="task not finished - cannot download files")

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
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@router.get("/{task_id}/geneRes", response_model=List[MoleculeResponse])
async def get_generated_molecules(request: Request, task_id: str):
    """
    获取单个 generate 任务的 output.json，并以 List[MoleculeOutput] 格式返回。
    """
    current_user = request.state.user
    logger.info("User %s requesting generated molecules for task %s", current_user.username, task_id)
    task = TaskService.get_task(task_id)

    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "generate":
        raise HTTPException(status_code=400, detail="task type is not generate")
    if task.status != "finished":
        raise HTTPException(status_code=202, detail="task is still processing")

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
    logger.info("User %s requesting docking results for task %s", current_user.username, task_id)
    task = TaskService.get_task(task_id)

    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="task type is not docking")
    if task.status != "finished":
        raise HTTPException(status_code=202, detail="task is still processing")

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
    logger.info("User %s requesting SDF file %s for task %s", current_user.username, filename, task_id)
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="task type is not docking")
    if task.status != "finished":
        raise HTTPException(status_code=202, detail="task is still processing")
    
    # 验证文件名格式，防止路径遍历攻击
    if not filename.endswith('.sdf') or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    
    # 构建SDF文件路径
    sdf_path = Path(task.job_dir) / "docked" / filename
    if not sdf_path.exists():
        raise HTTPException(status_code=404, detail="SDF file not found")
    
    # 返回SDF文件内容
    return FileResponse(
        path=str(sdf_path),
        media_type="chemical/x-mdl-sdfile",
        filename=filename
    )


@router.get("/{task_id}/protein")
async def get_protein_file(request: Request, task_id: str):
    """
    获取docking任务使用的protein文件内容
    """
    current_user = request.state.user
    logger.info("User %s requesting protein file for task %s", current_user.username, task_id)
    
    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.task_type != "docking":
        raise HTTPException(status_code=400, detail="task type is not docking")
    if task.status != "finished":
        raise HTTPException(status_code=202, detail="task is still processing")
    
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
        
        # 返回protein文件内容
        return FileResponse(
            path=str(protein_file_path),
            media_type="chemical/x-pdbqt",
            filename=protein_file_path.name
        )
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="invalid dockRes format")
    except Exception as e:
        logger.exception("Error getting protein file: %s", e)
        raise HTTPException(status_code=500, detail=f"error getting protein file: {e}")
