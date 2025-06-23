import json
from pathlib import Path
import shutil
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import pandas as pd

from Vina.vina_workflow import vina_docking_from_list
from config import ROOT
from database.services.task_service import TaskService
from database.services.upload_service import UploadService
from security.auth import get_current_user
from utils.tools import DockingRequest


router = APIRouter(tags=["Smiles"])

@router.post("/docking")
async def docking_endpoint(
    request: DockingRequest,
    receptor_filename: Optional[str] = Query(
        None,
        description="用户在上传历史中已有的受体 pdbqt 文件名"
    ),
    current_user = Depends(get_current_user),
):
    """
    1. 校验 token，获取 current_user
    2. 如果提供 receptor_filename，就去 user_uploads 表查同名记录并取 file_path；否则使用默认资源
    3. 其余逻辑同之前
    """
    try:
        # —— 1) 确定受体文件路径 —— #
        if receptor_filename:
            # 查用户上传记录
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
            "ligands": [lig.model_dump() for lig in request.ligands],
            "receptor_pdbqt": receptor_path,
            "min_ph": request.min_ph,
            "max_ph": request.max_ph,
            "n_jobs": request.n_jobs,
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

    except HTTPException:
        # 直接抛出的 HTTPException，交给 FastAPI 处理
        raise
    except Exception as e:
        # 其他异常
        print(f"docking 失败: {e}")
        raise HTTPException(status_code=500, detail=f"docking 失败: {e}")
