from datetime import datetime
import io
from pathlib import Path
import json
from typing import List, Optional
import zipfile
import pandas as pd
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from database.services import TaskService
from utils.tools import MoleculeOutput

router = APIRouter(prefix="/tasks", tags=["Tasks"])

class TaskResponse(BaseModel):
    id: str
    user_id: str
    task_type: str
    job_dir: str
    status: str
    created_at: datetime
    finished_at: Optional[datetime]
    
@router.get("/{task_id}")
async def get_task_result(request: Request, task_id: str):
    # 从中间件注入的 state 中取出已验证的用户
    current_user = request.state.user

    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "finished":
        return {"status": task.status}

    job_dir = Path(task.job_dir)
    if task.task_type == "generate":
        output = job_dir / "output.json"
        if not output.exists():
            raise HTTPException(status_code=500, detail="output not found")
        with open(output, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content={"status": task.status, "result": data})

    elif task.task_type == "docking":
        csv_file = job_dir / "dockRes.csv"
        if not csv_file.exists():
            raise HTTPException(status_code=500, detail="result csv not found")
        df = pd.read_csv(csv_file)
        records = df.to_dict(orient="records")
        return JSONResponse(content={"status": task.status, "results": records})

    else:
        raise HTTPException(status_code=400, detail="unknown task type")

@router.get("/", response_model=List[TaskResponse])
async def list_user_tasks(request: Request):
    """
    列出当前登录用户提交的所有任务。
    """
    current_user = request.state.user
    tasks = TaskService.get_tasks_by_user(current_user.id)
    # 如果想在没有任务时返回 404，可以加：
    # if not tasks:
    #     raise HTTPException(status_code=404, detail="no tasks found for this user")
    return tasks

@router.get("/{task_id}/download")
async def download_task_files(request: Request, task_id: str):
    """Download result files of a finished task as a zip archive."""
    current_user = request.state.user

    task = TaskService.get_task(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="task not found")
    if task.status != "finished":
        raise HTTPException(status_code=400, detail="task not finished")

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

@router.get("/{task_id}/molecules", response_model=List[MoleculeOutput])
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
    if task.status != "finished":
        raise HTTPException(status_code=400, detail="task not finished")

    output_path = Path(task.job_dir) / "output.json"
    if not output_path.exists():
        raise HTTPException(status_code=500, detail="output not found")

    # 读取并解析 output.json，假设它是 List[dict] 且每个 dict 都符合 MoleculeOutput 的字段
    data = json.loads(output_path.read_text(encoding="utf-8"))
    return data