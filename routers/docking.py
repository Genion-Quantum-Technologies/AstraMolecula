import json
from pathlib import Path
import shutil
import uuid
import logging

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from database.services.task_service import TaskService
from database.services.upload_service import UploadService
from database.services.docking_task_params_service import DockingTaskParamsService
from requests.basic_request import DockingRequest
from services.storage import get_storage
from services.storage.config import StorageConfig
from config import ROOT

logger = logging.getLogger("docking_router")

router = APIRouter(tags=["Smiles"])

@router.post("/docking")
async def docking_endpoint(
    request: Request,
    docking_request: DockingRequest,
):
    # 从中间件注入的 state 中取出已验证的用户
    current_user = request.state.user
    
    # 从Body中获取receptor_filename
    receptor_filename = docking_request.receptor_filename
    
    # 详细日志：记录提交的任务参数
    ligand_info = [{"smiles": lig.smiles, "title": lig.title} for lig in docking_request.ligands]
    logger.info("User %s (user_id: %s) submit docking task with params: "
                "receptor_filename=%s, n_ligands=%d, ligands=%s, "
                "center=(%.2f, %.2f, %.2f), box_size=(%.2f, %.2f, %.2f), "
                "exhaustiveness=%d, n_poses=%d, n_jobs=%d, ph_range=(%.1f, %.1f)",
                current_user.username, current_user.id,
                receptor_filename, len(docking_request.ligands), ligand_info,
                docking_request.center_x, docking_request.center_y, docking_request.center_z,
                docking_request.box_size_x, docking_request.box_size_y, docking_request.box_size_z,
                docking_request.exhaustiveness, docking_request.n_poses, docking_request.n_jobs,
                docking_request.min_ph, docking_request.max_ph)

    try:
        # —— 1) 验证并确定受体文件路径 —— #
        # receptor_filename 从Body中获取，已经是必填参数
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
        
        # 获取存储服务并验证文件是否存在于 SeaweedFS
        storage = get_storage()
        remote_key = match.file_path  # 现在 file_path 存储的是 remote_key
        
        if not await storage.file_exists(remote_key):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "receptor_file_missing",
                    "message": f"受体文件 '{receptor_filename}' 在存储系统中不存在",
                    "details": {
                        "storage_key": remote_key,
                        "file_record_exists": True,
                        "suggestion": "请重新上传该文件"
                    }
                }
            )
        
        logger.info("User %s using receptor file: %s (storage_key: %s)", 
                   current_user.username, receptor_filename, remote_key)

        # —— 2) 创建作业目录结构（在 SeaweedFS 中） —— #
        job_id = uuid.uuid4().hex
        job_prefix = f"jobs/docking/{job_id}"
        
        # 本地临时目录用于计算（计算节点需要本地文件访问）
        local_job_dir = StorageConfig.TEMP_DIR / "jobs" / "docking" / job_id
        local_input_dir = local_job_dir / "input"
        local_output_dir = local_job_dir / "output"
        local_input_dir.mkdir(parents=True, exist_ok=True)
        local_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 下载受体文件到本地临时目录
        local_receptor_path = local_input_dir / receptor_filename
        await storage.download_file(remote_key, local_receptor_path)

        # —— 3) 保存请求参数 —— #
        params = {
            "ligands": [lig.model_dump() for lig in docking_request.ligands],
            "receptor_pdbqt": str(local_receptor_path),  # 本地临时路径
            "receptor_storage_key": remote_key,  # 存储路径，用于追溯
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
        
        # 添加存储相关元信息
        params["storage_prefix"] = job_prefix
        params["local_job_dir"] = str(local_job_dir)
            
        # 保存配置文件到本地临时目录
        local_input_json = local_input_dir / "input.json"
        with open(local_input_json, "w", encoding="utf-8") as f:
            json.dump(params, f, ensure_ascii=False, indent=2)
        
        # 同时上传 input.json 到 SeaweedFS
        await storage.upload_file(local_input_json, f"{job_prefix}/input/input.json")

        # —— 4) 创建任务 —— #
        # job_dir 现在存储的是 SeaweedFS 的路径前缀，同时在 storage_prefix 字段中也记录
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="docking",
            job_dir=str(local_job_dir)  # 本地临时目录，用于计算节点访问
        )

        # —— 4.1) 创建任务参数记录并计算成本 —— #
        try:
            task_params = DockingTaskParamsService.create_task_params(
                task_id=task_id,
                n_ligands=len(docking_request.ligands),
                min_ph=docking_request.min_ph,
                max_ph=docking_request.max_ph,
                center_x=docking_request.center_x,
                center_y=docking_request.center_y,
                center_z=docking_request.center_z,
                box_size_x=docking_request.box_size_x,
                box_size_y=docking_request.box_size_y,
                box_size_z=docking_request.box_size_z,
                exhaustiveness=docking_request.exhaustiveness,
                n_poses=docking_request.n_poses,
                n_jobs=docking_request.n_jobs
            )
            logger.info("Task %s: Estimated compute units: %.2f", task_id, task_params.total_compute_units)
        except Exception as e:
            logger.error("Failed to create task params for task %s: %s", task_id, e)
            # 即使参数保存失败，也继续执行任务
            task_params = None

        # —— 4.5) 任务已创建，交给 dockingVinaApp 处理 —— #
        logger.info("Docking task %s created and delegated to dockingVinaApp", task_id)

        # —— 5) 返回详细的响应信息 —— #
        response_data = {
            "task_id": task_id,
            "status": "submitted",
            "message": "对接任务已成功提交",
            "details": {
                "job_id": job_id,
                "storage_prefix": job_prefix,
                "receptor_file": receptor_filename,
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
                "download_files": f"/tasks/{task_id}/download",
                "get_cost_info": f"/tasks/{task_id}/cost"
            }
        }
        
        # 添加成本信息（如果可用）
        if task_params:
            cost_summary = DockingTaskParamsService.get_cost_summary(task_id)
            if cost_summary:
                response_data["cost_estimate"] = {
                    "total_compute_units": cost_summary["compute_units"]["total"],
                    "per_ligand_cost": cost_summary["compute_units"]["per_ligand"],
                    "complexity_category": cost_summary["comparison"]["category"],
                    "estimated_molecules": cost_summary["input_summary"]["estimated_molecules"]
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


@router.post("/docking/estimate-cost")
async def estimate_docking_cost(
    request: Request,
    docking_request: DockingRequest
):
    """
    预估 docking 任务成本（不创建实际任务）
    """
    # 从中间件注入的 state 中取出已验证的用户
    current_user = request.state.user
    logger.info("User %s requesting cost estimate", current_user.username)

    try:
        # 使用服务层进行成本预估
        cost_estimate = DockingTaskParamsService.estimate_cost_before_submission(
            n_ligands=len(docking_request.ligands),
            min_ph=docking_request.min_ph,
            max_ph=docking_request.max_ph,
            center_x=docking_request.center_x,
            center_y=docking_request.center_y,
            center_z=docking_request.center_z,
            box_size_x=docking_request.box_size_x,
            box_size_y=docking_request.box_size_y,
            box_size_z=docking_request.box_size_z,
            exhaustiveness=docking_request.exhaustiveness,
            n_poses=docking_request.n_poses,
            n_jobs=docking_request.n_jobs
        )

        response_data = {
            "status": "success",
            "message": "成本预估完成",
            "cost_estimate": cost_estimate,
            "disclaimer": "这是基于理论模型的估算，实际执行时间可能因硬件和系统负载而有所不同"
        }

        return JSONResponse(content=response_data, status_code=200)

    except Exception as e:
        logger.exception("Cost estimation failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "cost_estimation_failed",
                "message": "成本预估失败",
                "details": {
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            }
        )

