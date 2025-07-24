import json
from pathlib import Path
import shutil
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import JSONResponse

from Vina.vina_workflow import vina_docking_from_list
from database.services.task_service import TaskService
from database.services.upload_service import UploadService
from requests.basic_request import DockingRequest
import config

logger = logging.getLogger("docking_router")

router = APIRouter(tags=["Smiles"])

@router.post("/docking")
async def docking_endpoint(
    request: Request,
    docking_request: DockingRequest,
    receptor_filename: Optional[str] = Query(
        None,
        description="用户在上传历史中已有的受体 pdbqt 文件名",
        regex=r"^[a-zA-Z0-9_.-]+\.pdbqt$"
    ),
):
    # 从中间件注入的 state 中取出已验证的用户
    current_user = request.state.user
    logger.info("User %s submit docking task", current_user.username)

    try:
        # —— 1) 验证并确定受体文件路径 —— #
        if receptor_filename:
            # 验证文件名格式
            if not receptor_filename.endswith('.pdbqt'):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "invalid_receptor_filename",
                        "message": f"受体文件必须是.pdbqt格式，当前文件: {receptor_filename}",
                        "details": {
                            "provided_filename": receptor_filename,
                            "required_extension": ".pdbqt",
                            "valid_example": "protein_7UDP.pdbqt"
                        }
                    }
                )
            
            # 检查是否包含非法字符
            if any(char in receptor_filename for char in ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*']):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "invalid_receptor_filename",
                        "message": "文件名包含非法字符",
                        "details": {
                            "provided_filename": receptor_filename,
                            "forbidden_chars": ['/', '\\', '..', '<', '>', ':', '"', '|', '?', '*'],
                            "suggestion": "请使用只包含字母、数字、下划线、点号和短横线的文件名"
                        }
                    }
                )
                
            # 查找用户上传的文件
            uploads = UploadService.list_by_user(current_user.id)
            match = next((u for u in uploads if u.filename == receptor_filename), None)
            
            if not match:
                available_files = [u.filename for u in uploads if u.filename.endswith('.pdbqt')]
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": "receptor_file_not_found",
                        "message": f"受体文件 '{receptor_filename}' 不在你的上传记录中",
                        "details": {
                            "requested_file": receptor_filename,
                            "available_pdbqt_files": available_files,
                            "total_uploaded_files": len(uploads),
                            "suggestion": "请先上传PDBQT文件或使用已上传的文件" if available_files else "请先上传PDBQT文件"
                        }
                    }
                )
            
            # 验证文件是否实际存在
            receptor_path = Path(match.file_path)
            if not receptor_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "receptor_file_missing",
                        "message": f"受体文件 '{receptor_filename}' 在服务器上不存在",
                        "details": {
                            "expected_path": str(receptor_path),
                            "file_record_exists": True,
                            "suggestion": "请重新上传该文件"
                        }
                    }
                )
            
            receptor_path = str(receptor_path)
        else:
            # 使用默认受体文件
            default_receptor_path = config.ROOT / "resource" / "protein_7UDP.pdbqt"
            if not default_receptor_path.exists():
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "default_receptor_missing",
                        "message": "默认受体文件不存在",
                        "details": {
                            "expected_path": str(default_receptor_path),
                            "suggestion": "请提供receptor_filename参数指定自定义受体文件"
                        }
                    }
                )
            receptor_path = str(default_receptor_path)

        # —— 2) 创建作业目录 —— #
        JOBS_DOCK_DIR = config.ROOT / "jobs" / "docking"
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
        
        # 添加中心坐标参数
        params["center_x"] = docking_request.center_x
        params["center_y"] = docking_request.center_y
        params["center_z"] = docking_request.center_z
            
        # 添加盒子大小参数 (必填的xyz三个维度)
        params["box_size_x"] = docking_request.box_size_x
        params["box_size_y"] = docking_request.box_size_y
        params["box_size_z"] = docking_request.box_size_z
            
        # 添加其他必填参数
        params["exhaustiveness"] = docking_request.exhaustiveness
        params["n_poses"] = docking_request.n_poses
            
        with open(job_dir / "input.json", "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)

        # —— 4) 创建任务 —— #
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="docking",
            job_dir=str(job_dir)
        )

        # —— 4.5) 启动异步处理 —— #
        try:
            from async_task_processor import task_processor
            task = TaskService.get_task(task_id)
            if task:
                # 在后台启动任务处理
                import asyncio
                asyncio.create_task(task_processor.process_task(task))
                logger.info("Started async processing for task %s", task_id)
            else:
                logger.error("Failed to retrieve created task %s", task_id)
        except Exception as e:
            logger.error("Failed to start async processing for task %s: %s", task_id, e)
            # 即使启动失败，也返回任务ID，让旧的轮询机制处理

        # —— 5) 返回详细的响应信息 —— #
        response_data = {
            "task_id": task_id,
            "status": "submitted",
            "message": "对接任务已成功提交",
            "details": {
                "job_id": job_id,
                "job_directory": str(job_dir),
                "receptor_file": receptor_path,
                "ligands_count": len(docking_request.ligands),
                "ligand_titles": [lig.title for lig in docking_request.ligands],
                "parameters": {
                    "center": {
                        "x": docking_request.center_x,
                        "y": docking_request.center_y,
                        "z": docking_request.center_z
                    },
                    "box_size": {
                        "x": docking_request.box_size_x,
                        "y": docking_request.box_size_y,
                        "z": docking_request.box_size_z
                    },
                    "ph_range": {
                        "min": docking_request.min_ph,
                        "max": docking_request.max_ph
                    },
                    "n_jobs": docking_request.n_jobs,
                    "exhaustiveness": docking_request.exhaustiveness,
                    "n_poses": docking_request.n_poses
                }
            },
            "next_steps": {
                "check_status": f"/tasks/{task_id}",
                "get_results": f"/tasks/{task_id}/dockRes",
                "download_files": f"/tasks/{task_id}/download"
            }
        }
        return JSONResponse(content=response_data, status_code=201)

    except HTTPException:
        # 重新抛出 HTTPException，保持原有的错误信息
        raise
    except Exception as e:
        logger.exception("docking 失败: %s", e)
        raise HTTPException(
            status_code=500, 
            detail={
                "error": "internal_server_error",
                "message": "对接任务提交失败",
                "details": {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "suggestion": "请检查请求参数或联系系统管理员"
                }
            }
        )

