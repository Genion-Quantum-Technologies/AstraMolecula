"""
SARM 分析 API 路由

提供两种任务类型：
- POST /sarm/analyze  — 创建 SARM 矩阵生成任务
- POST /sarm/tree     — 创建 SAR 树生成任务
- GET  /sarm/{task_id}        — 查询任务状态
- GET  /sarm/{task_id}/params — 查询任务参数
- GET  /sarm/{task_id}/results — 列出结果文件
- GET  /sarm/{task_id}/download — 打包下载结果
"""
import io
import json
import uuid
import logging
import zipfile
from typing import List, Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from astra_molecula.db.services import TaskService
from astra_molecula.db.services.upload_service import UploadService
from astra_molecula.db.services.sarm_task_params_service import SarmTaskParamsService
from astra_molecula.schemas.requests.basic_request import SarmAnalysisRequest, SarmTreeRequest
from astra_molecula.schemas.responses.basic_response import TaskResponse
from astra_molecula.services.storage import get_storage
from astra_molecula.core.config import ROOT

logger = logging.getLogger("sarm_router")

router = APIRouter(prefix="/sarm", tags=["SARM Analysis"])


# ==== 辅助函数 ====

def _normalize_storage_prefix(job_dir: str) -> str:
    """标准化 job_dir 为 SeaweedFS 存储前缀"""
    if not job_dir:
        return job_dir
    if job_dir.startswith('/'):
        if '/jobs/' in job_dir:
            idx = job_dir.index('/jobs/') + 1
            return job_dir[idx:]
    return job_dir


def _get_current_user(request: Request):
    """获取当前认证用户"""
    if not hasattr(request.state, 'user') or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return request.state.user


# ==== 任务创建接口 ====

@router.post("/analyze",
             summary="创建 SARM 矩阵分析任务",
             description="提交 SARM 矩阵分析任务到队列。需要先通过 /uploads 上传包含 SMILES 和活性数据的 CSV 文件。")
async def create_sarm_analysis(request: Request, sarm_request: SarmAnalysisRequest):
    """
    创建 SARM 矩阵分析任务。

    流程：
    1. 验证用户上传的 CSV 文件存在
    2. 将 CSV 文件复制到任务专属存储路径
    3. 在 tasks 表创建任务记录 (task_type='sarm_analysis')
    4. 在 sarm_task_params 表写入任务参数 (task_subtype='sarm')
    5. autoSARM Worker 将自动轮询处理此任务

    必填参数：
    - csv_filename: 已上传的 CSV 文件名（通过 /uploads 上传）
    - value_columns: CSV 中用于 SAR 分析的数值活性列名列表

    可选参数：
    - analysis_type: 分析类型（默认 'smiles'）
    - log_transform: 是否对数变换（默认 false）
    - minimum_site1/minimum_site2: 片段最小出现次数（默认 3）
    - n_jobs: 并行进程数（默认自动检测）
    - csv2excel: 是否导出 Excel（默认 false）
    """
    current_user = _get_current_user(request)

    logger.info("User %s (user_id: %s) submitting SARM analysis task: "
                "csv_filename=%s, value_columns=%s, analysis_type=%s, "
                "log_transform=%s, minimum_site1=%s, minimum_site2=%s, csv2excel=%s",
                current_user.username, current_user.id,
                sarm_request.csv_filename, sarm_request.value_columns,
                sarm_request.analysis_type, sarm_request.log_transform,
                sarm_request.minimum_site1, sarm_request.minimum_site2,
                sarm_request.csv2excel)

    try:
        # —— 1) 验证 CSV 文件名格式 —— #
        csv_filename = sarm_request.csv_filename
        if not csv_filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_csv_filename",
                    "message": f"文件必须是 .csv 格式，当前文件: {csv_filename}",
                    "details": {
                        "provided_filename": csv_filename,
                        "required_extension": ".csv"
                    }
                }
            )

        # 验证 value_columns 非空
        if not sarm_request.value_columns:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "empty_value_columns",
                    "message": "value_columns 不能为空，需要至少指定一个活性数据列名",
                    "details": {
                        "suggestion": "例如: [\"IC50_uM\"] 或 [\"IC50\", \"Ki\"]"
                    }
                }
            )

        # 验证 analysis_type
        if sarm_request.analysis_type not in ("smiles", "scaffold"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_analysis_type",
                    "message": f"analysis_type 必须是 'smiles' 或 'scaffold'，当前值: {sarm_request.analysis_type}",
                    "details": {
                        "valid_values": ["smiles", "scaffold"]
                    }
                }
            )

        # —— 2) 验证文件在用户上传记录中 —— #
        uploads = UploadService.list_by_user(current_user.id)
        match = next((u for u in uploads if u.filename == csv_filename), None)

        if not match:
            available_csv_files = [u.filename for u in uploads if u.filename.endswith('.csv')]
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "csv_file_not_found",
                    "message": f"CSV 文件 '{csv_filename}' 不在你的上传记录中",
                    "details": {
                        "requested_file": csv_filename,
                        "available_csv_files": available_csv_files,
                        "suggestion": "请先通过 /uploads 上传 CSV 文件" if not available_csv_files else "请使用已上传的文件或重新上传"
                    }
                }
            )

        # —— 3) 验证文件在 SeaweedFS 中存在 —— #
        storage = get_storage()
        remote_key = match.file_path

        if not await storage.file_exists(remote_key):
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "csv_file_missing",
                    "message": f"CSV 文件 '{csv_filename}' 在存储系统中不存在",
                    "details": {
                        "storage_key": remote_key,
                        "suggestion": "请重新上传该文件"
                    }
                }
            )

        logger.info("User %s using CSV file: %s (storage_key: %s)",
                    current_user.username, csv_filename, remote_key)

        # —— 4) 创建任务存储路径并复制文件 —— #
        job_id = str(uuid.uuid4())
        job_prefix = f"jobs/sarm_analysis/{job_id}"

        # 将用户上传的 CSV 复制到任务专属输入目录
        target_key = f"{job_prefix}/input/{csv_filename}"
        await storage.copy_file(remote_key, target_key)
        logger.info("CSV file copied to task input: %s -> %s", remote_key, target_key)

        # —— 5) 在 tasks 表创建任务记录 —— #
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="sarm_analysis",
            job_dir=job_prefix  # SeaweedFS 路径前缀
        )

        # —— 6) 在 sarm_task_params 表写入参数 —— #
        try:
            sarm_params = SarmTaskParamsService.create_sarm_params(
                task_id=task_id,
                csv_filename=csv_filename,
                value_columns=sarm_request.value_columns,
                analysis_type=sarm_request.analysis_type,
                log_transform=sarm_request.log_transform,
                minimum_site1=sarm_request.minimum_site1,
                minimum_site2=sarm_request.minimum_site2,
                n_jobs=sarm_request.n_jobs,
                csv2excel=sarm_request.csv2excel
            )
            logger.info("SARM task params created for task %s", task_id)
        except Exception as e:
            logger.error("Failed to create SARM task params for task %s: %s", task_id, e)
            # 参数记录失败不影响任务执行（worker 也会读取默认值）

        # —— 7) 返回响应 —— #
        response_data = {
            "task_id": task_id,
            "status": "submitted",
            "message": "SARM 矩阵分析任务已成功提交",
            "details": {
                "job_id": job_id,
                "storage_prefix": job_prefix,
                "csv_filename": csv_filename,
                "value_columns": sarm_request.value_columns,
                "parameters": {
                    "analysis_type": sarm_request.analysis_type,
                    "log_transform": sarm_request.log_transform,
                    "minimum_site1": sarm_request.minimum_site1,
                    "minimum_site2": sarm_request.minimum_site2,
                    "n_jobs": sarm_request.n_jobs,
                    "csv2excel": sarm_request.csv2excel
                }
            },
            "next_steps": {
                "check_status": f"/sarm/{task_id}",
                "get_params": f"/sarm/{task_id}/params",
                "list_results": f"/sarm/{task_id}/results",
                "download_results": f"/sarm/{task_id}/download"
            }
        }

        return JSONResponse(content=response_data, status_code=201)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("SARM analysis task submission failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_server_error",
                "message": "SARM 分析任务提交失败",
                "details": {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "suggestion": "请检查请求参数或联系系统管理员"
                }
            }
        )


@router.post("/tree",
             summary="创建 SAR 树生成任务",
             description="提交 SAR 树生成任务到队列。通常在 SARM 矩阵分析完成后使用，依赖先前分析结果。")
async def create_sarm_tree(request: Request, tree_request: SarmTreeRequest):
    """
    创建 SAR 树生成任务。

    必填参数：
    - fragment_core: 核心片段 SMARTS/SMILES
    - root_title: 根节点显示名称

    可选参数：
    - input_file: 输入数据文件名（默认 'input.csv'）
    - tree_content: 树展示内容类型（默认 ['double-cut']）
    - highlight_dict: 高亮配置列表（默认 []）
    - max_level: 最大展开层数（默认 5，建议 3-7）
    """
    current_user = _get_current_user(request)

    logger.info("User %s (user_id: %s) submitting SAR tree task: "
                "fragment_core=%s, root_title=%s, max_level=%d",
                current_user.username, current_user.id,
                tree_request.fragment_core, tree_request.root_title,
                tree_request.max_level)

    try:
        # 验证 fragment_core 非空
        if not tree_request.fragment_core.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "empty_fragment_core",
                    "message": "fragment_core 不能为空",
                    "details": {
                        "suggestion": "请提供用于构建衍生树的核心片段 SMARTS/SMILES"
                    }
                }
            )

        # 验证 root_title 非空
        if not tree_request.root_title.strip():
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "empty_root_title",
                    "message": "root_title 不能为空",
                    "details": {
                        "suggestion": "请提供 SAR 树根节点的显示名称"
                    }
                }
            )

        # 验证 max_level 范围
        if tree_request.max_level < 1 or tree_request.max_level > 20:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_max_level",
                    "message": f"max_level 必须在 1-20 之间，当前值: {tree_request.max_level}",
                    "details": {
                        "suggestion": "建议设置为 3-7，层数越多计算越慢"
                    }
                }
            )

        # —— 验证前序 SARM 分析任务 —— #
        source_task_id = tree_request.source_task_id.strip()
        if not source_task_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "empty_source_task_id",
                    "message": "source_task_id 不能为空，需要提供前序 SARM 矩阵分析任务 ID",
                    "details": {
                        "suggestion": "请先通过 /sarm/analyze 提交 SARM 矩阵分析任务，待任务完成后使用其 task_id"
                    }
                }
            )

        source_task = TaskService.get_task(source_task_id)
        if not source_task:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "source_task_not_found",
                    "message": f"前序任务 '{source_task_id}' 不存在",
                    "details": {"source_task_id": source_task_id}
                }
            )

        if source_task.task_type != "sarm_analysis":
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_source_task_type",
                    "message": f"前序任务类型必须是 sarm_analysis，当前: {source_task.task_type}",
                }
            )

        if source_task.status != "finished":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "source_task_not_finished",
                    "message": f"前序 SARM 分析任务尚未完成，当前状态: {source_task.status}",
                    "details": {"current_status": source_task.status}
                }
            )

        source_job_dir = _normalize_storage_prefix(source_task.job_dir)
        logger.info("Source SARM task %s, job_dir=%s", source_task_id, source_job_dir)

        # —— 创建任务存储路径 —— #
        job_id = str(uuid.uuid4())
        job_prefix = f"jobs/sarm_analysis/{job_id}"

        # —— 复制前序 SARM 分析结果到新任务 —— #
        storage = get_storage()
        try:
            # 复制 input.csv（SARM 分析生成的输入数据）
            source_input_key = f"{source_job_dir}/output/SAR_Results/input.csv"
            target_input_key = f"{job_prefix}/input/{tree_request.input_file}"
            await storage.copy_file(source_input_key, target_input_key)
            logger.info("Copied input.csv: %s -> %s", source_input_key, target_input_key)

            # 复制 SAR_Results 目录下的所有结果文件
            source_results_prefix = f"{source_job_dir}/output/SAR_Results"
            target_results_prefix = f"{job_prefix}/output/SAR_Results"
            copied_count = await storage.copy_directory(source_results_prefix, target_results_prefix)
            logger.info("Copied %d SAR result files to new tree task", copied_count)
        except Exception as e:
            logger.error("Failed to copy SARM results for tree task: %s", e)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "copy_results_failed",
                    "message": "复制前序 SARM 分析结果失败",
                    "details": {
                        "source_task_id": source_task_id,
                        "error_message": str(e)
                    }
                }
            )

        # —— 在 tasks 表创建任务记录 —— #
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="sarm_analysis",
            job_dir=job_prefix
        )

        # —— 在 sarm_task_params 表写入参数 —— #
        try:
            tree_params = SarmTaskParamsService.create_tree_params(
                task_id=task_id,
                fragment_core=tree_request.fragment_core,
                root_title=tree_request.root_title,
                input_file=tree_request.input_file,
                tree_content=tree_request.tree_content,
                highlight_dict=tree_request.highlight_dict,
                max_level=tree_request.max_level
            )
            logger.info("SAR tree params created for task %s", task_id)
        except Exception as e:
            logger.error("Failed to create SAR tree params for task %s: %s", task_id, e)

        # —— 返回响应 —— #
        response_data = {
            "task_id": task_id,
            "status": "submitted",
            "message": "SAR 树生成任务已成功提交",
            "details": {
                "job_id": job_id,
                "storage_prefix": job_prefix,
                "parameters": {
                    "fragment_core": tree_request.fragment_core,
                    "root_title": tree_request.root_title,
                    "input_file": tree_request.input_file,
                    "tree_content": tree_request.tree_content,
                    "highlight_dict": tree_request.highlight_dict,
                    "max_level": tree_request.max_level
                }
            },
            "next_steps": {
                "check_status": f"/sarm/{task_id}",
                "get_params": f"/sarm/{task_id}/params",
                "list_results": f"/sarm/{task_id}/results",
                "download_results": f"/sarm/{task_id}/download"
            }
        }

        return JSONResponse(content=response_data, status_code=201)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("SAR tree task submission failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_server_error",
                "message": "SAR 树生成任务提交失败",
                "details": {
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "suggestion": "请检查请求参数或联系系统管理员"
                }
            }
        )


# ==== 任务查询接口 ====

@router.get("/{task_id}",
            response_model=TaskResponse,
            summary="查询 SARM 任务状态",
            description="获取指定 SARM 分析任务的状态和基本信息")
async def get_sarm_task_status(request: Request, task_id: str):
    """查询 SARM 分析任务的状态"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.task_type != "sarm_analysis":
            raise HTTPException(status_code=400, detail="Task is not a SARM analysis task")

        return TaskResponse(
            id=task.id,
            user_id=task.user_id,
            task_type=task.task_type,
            job_dir=task.job_dir,
            status=task.status,
            created_at=task.created_at,
            finished_at=task.finished_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching SARM task %s for user %s: %s",
                    task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")


@router.get("/{task_id}/params",
            summary="查询 SARM 任务参数",
            description="获取 SARM 分析任务的配置参数详情")
async def get_sarm_task_params(request: Request, task_id: str):
    """查询 SARM 分析任务的配置参数"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.task_type != "sarm_analysis":
            raise HTTPException(status_code=400, detail="Task is not a SARM analysis task")

        params = SarmTaskParamsService.get_task_params(task_id)
        if not params:
            raise HTTPException(status_code=404, detail="SARM task parameters not found")

        # 构建响应，解析 JSON 字段
        result = {
            "task_id": task_id,
            "task_subtype": params.task_subtype,
        }

        if params.task_subtype == "sarm":
            result.update({
                "csv_filename": params.csv_filename,
                "analysis_type": params.analysis_type,
                "value_columns": json.loads(params.value_columns) if params.value_columns else [],
                "log_transform": params.log_transform,
                "minimum_site1": float(params.minimum_site1) if params.minimum_site1 is not None else 3,
                "minimum_site2": float(params.minimum_site2) if params.minimum_site2 is not None else 3,
                "n_jobs": params.n_jobs,
                "csv2excel": params.csv2excel
            })
        elif params.task_subtype == "tree":
            result.update({
                "fragment_core": params.fragment_core,
                "root_title": params.root_title,
                "input_file": params.input_file,
                "tree_content": json.loads(params.tree_content) if params.tree_content else ["double-cut"],
                "highlight_dict": json.loads(params.highlight_dict) if params.highlight_dict else [],
                "max_level": params.max_level
            })

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching SARM task params %s for user %s: %s",
                    task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task parameters")


# ==== 结果查询和下载接口 ====

@router.get("/{task_id}/results",
            summary="列出 SARM 结果文件",
            description="列出任务完成后 SAR_Results 目录下的所有结果文件")
async def list_sarm_results(request: Request, task_id: str):
    """
    列出 SARM 分析结果文件。

    任务完成后，结果存储在 SeaweedFS 的 output/SAR_Results/ 目录下，
    包括 Left_Table/、Right_Table/、Combine_Table/ 等子目录和 info CSV 文件。
    """
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.task_type != "sarm_analysis":
            raise HTTPException(status_code=400, detail="Task is not a SARM analysis task")

        if task.status != "finished":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "task_not_finished",
                    "message": f"任务状态为 {task.status}，尚未完成",
                    "details": {
                        "current_status": task.status,
                        "suggestion": "请等待任务完成后再查看结果"
                    }
                }
            )

        # 从 SeaweedFS 列出结果文件
        storage = get_storage()
        storage_prefix = _normalize_storage_prefix(task.job_dir)
        results_prefix = f"{storage_prefix}/output/SAR_Results/"

        files = await storage.list_files(results_prefix)

        if not files:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "no_results_found",
                    "message": "未找到结果文件",
                    "details": {
                        "storage_prefix": results_prefix,
                        "suggestion": "结果可能尚未生成完成，请稍后重试"
                    }
                }
            )

        # 整理文件列表，提取相对路径
        result_files = []
        for file_key in files:
            if file_key.endswith('/'):
                continue  # 跳过目录
            relative_path = file_key[len(results_prefix):] if file_key.startswith(results_prefix) else file_key.split('SAR_Results/')[-1]
            file_info = await storage.get_file_info(file_key)
            result_files.append({
                "filename": relative_path,
                "storage_key": file_key,
                "size": file_info.get("Content-Length") if file_info else None
            })

        return {
            "task_id": task_id,
            "status": task.status,
            "total_files": len(result_files),
            "files": result_files,
            "download_all": f"/sarm/{task_id}/download"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing SARM results for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to list result files")


@router.get("/{task_id}/download",
            summary="打包下载 SARM 结果",
            description="将任务的所有结果文件打包为 ZIP 下载")
async def download_sarm_results(request: Request, task_id: str):
    """
    将 SARM 分析结果文件打包为 ZIP 下载。

    打包 output/SAR_Results/ 目录下的所有文件，
    包括各个 Table 子目录和 info CSV 文件。
    """
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.task_type != "sarm_analysis":
            raise HTTPException(status_code=400, detail="Task is not a SARM analysis task")

        if task.status != "finished":
            raise HTTPException(
                status_code=409,
                detail=f"Task status is {task.status}, cannot download results"
            )

        # 从 SeaweedFS 获取结果文件并打包
        storage = get_storage()
        storage_prefix = _normalize_storage_prefix(task.job_dir)
        results_prefix = f"{storage_prefix}/output/SAR_Results/"

        files = await storage.list_files(results_prefix)

        if not files:
            raise HTTPException(status_code=404, detail="No result files found")

        # 创建 ZIP 包
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_key in files:
                if file_key.endswith('/'):
                    continue  # 跳过目录

                try:
                    content = await storage.download_bytes(file_key)
                    # 使用相对路径作为 ZIP 内的文件名
                    arcname = file_key[len(results_prefix):] if file_key.startswith(results_prefix) else file_key.split('SAR_Results/')[-1]
                    zf.writestr(arcname, content)
                except Exception as e:
                    logger.warning("Failed to add file to ZIP: %s, error: %s", file_key, e)

        zip_buffer.seek(0)

        filename = f"sarm_results_{task_id}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading SARM results for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to download result files")


@router.get("/{task_id}/download/{file_path:path}",
            summary="下载单个结果文件",
            description="从 SAR_Results 目录下载指定的单个文件")
async def download_single_sarm_file(request: Request, task_id: str, file_path: str):
    """
    下载 SARM 结果中的单个文件。

    file_path 是相对于 SAR_Results/ 的路径，例如：
    - Left_Table_info.csv
    - Left_Table/some_file.csv
    - Combine_Table/combined_results.csv
    """
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        if task.task_type != "sarm_analysis":
            raise HTTPException(status_code=400, detail="Task is not a SARM analysis task")

        if task.status != "finished":
            raise HTTPException(
                status_code=409,
                detail=f"Task status is {task.status}, cannot download results"
            )

        # 安全检查：防止路径遍历
        if '..' in file_path or file_path.startswith('/'):
            raise HTTPException(status_code=400, detail="Invalid file path")

        storage = get_storage()
        storage_prefix = _normalize_storage_prefix(task.job_dir)
        remote_key = f"{storage_prefix}/output/SAR_Results/{file_path}"

        if not await storage.file_exists(remote_key):
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        content = await storage.download_bytes(remote_key)

        # 根据文件扩展名确定 MIME 类型
        filename = file_path.split('/')[-1]
        if filename.endswith('.csv'):
            media_type = "text/csv"
        elif filename.endswith('.xlsx'):
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif filename.endswith('.json'):
            media_type = "application/json"
        else:
            media_type = "application/octet-stream"

        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading SARM file %s for task %s: %s",
                    file_path, task_id, e)
        raise HTTPException(status_code=500, detail="Failed to download file")
