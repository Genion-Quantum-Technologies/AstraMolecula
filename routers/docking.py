import json
from pathlib import Path
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

from Vina.vina_workflow import vina_docking_from_list
from config import ROOT
from database.services.task_service import TaskService
from database.services.upload_service import UploadService
from utils.tools import DockingRequest

router = APIRouter(tags=["Smiles"])

@router.post("/docking")
async def docking_endpoint(
    request: Request,
    docking_request: DockingRequest,
    receptor_filename: Optional[str] = Query(
        None,
        description="用户在上传历史中已有的受体 pdbqt 文件名"
    ),
):
    # 从中间件注入的 state 中取出已验证的用户
    current_user = request.state.user

    try:
        # —— 1) 确定受体文件路径 —— #
        if receptor_filename:
            uploads = UploadService.list_by_user(current_user.id)
            match = next((u for u in uploads if u.filename == receptor_filename), None)
            if not match:
                raise HTTPException(
                    status_code=400,
                    detail=f"受体文件 '{receptor_filename}' 不在你的上传记录中"
                )
            receptor_path = match.file_path
        else:
            receptor_path = str(ROOT / "resource" / "protein_7UDP.pdbqt")

        # —— 2) 创建作业目录 —— #
        JOBS_DOCK_DIR = ROOT / "jobs" / "docking"
        JOBS_DOCK_DIR.mkdir(parents=True, exist_ok=True)
        job_id = uuid.uuid4().hex
        job_dir = JOBS_DOCK_DIR / job_id
        job_dir.mkdir()

        # —— 3) 保存请求参数 —— #
        params = {
            "ligands": [lig.model_dump() for lig in docking_request.ligands],
            "receptor_pdbqt": receptor_path,
            "min_ph": docking_request.min_ph,
            "max_ph": docking_request.max_ph,
            "n_jobs": docking_request.n_jobs,
        }
        with open(job_dir / "input.json", "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        # —— 4) 创建任务 —— #
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="docking",
            job_dir=str(job_dir)
        )

        # —— 5) 返回 task_id —— #
        return JSONResponse(content={"task_id": task_id})

    except Exception as e:
        # 其他异常
        print(f"docking 失败: {e}")
        raise HTTPException(status_code=500, detail=f"docking 失败: {e}")
