"""
HighFold-C2C 环肽设计 API 路由

提供以下接口：
- POST /highfold/predict          — 创建 HighFold-C2C 环肽设计任务
- GET  /highfold/{task_id}        — 查询任务状态
- GET  /highfold/{task_id}/params — 查询任务参数
- GET  /highfold/{task_id}/results — 获取结果摘要（CSV 解析为 JSON）
- GET  /highfold/{task_id}/results/csv — 下载原始 CSV
- GET  /highfold/{task_id}/sequences — 获取 FASTA 序列
- GET  /highfold/{task_id}/structures — 列出 PDB 结构文件
- GET  /highfold/{task_id}/structures/{filename} — 下载单个 PDB 文件
- GET  /highfold/{task_id}/download — 打包下载所有输出
"""
import io
import json
import re
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

from astra_molecula.db.services import TaskService
from astra_molecula.db.services.highfold_task_params_service import HighFoldTaskParamsService
from astra_molecula.schemas.requests.basic_request import HighFoldC2CRequest
from astra_molecula.schemas.responses.basic_response import TaskResponse
from astra_molecula.services.storage import get_storage
from astra_molecula.services import highfold_results
from astra_molecula.core.config import api as api_config

logger = logging.getLogger("highfold_router")

router = APIRouter(prefix="/highfold", tags=["HighFold C2C"])

# 前端基础 URL（用于生成公开 3D 查看分享链接），与 tasks.py 的 docking share_url 一致
FRONTEND_BASE_URL = api_config.frontend_base_url


def _public_viewer_base(request: Request) -> str:
    """计算公开查看页基础地址，镜像 docking dockRes 的 base_url 逻辑：
    优先用 FRONTEND_BASE_URL 环境变量，否则回退到请求的 scheme+host。"""
    base_url = FRONTEND_BASE_URL or f"{request.url.scheme}://{request.url.hostname}"
    return f"{base_url}/public/highfold-viewer"

# ==== 参数约束常量（单一来源）====
# 后端是约束的权威来源；前端通过 GET /highfold/constraints 拉取这些值做预校验回显，
# 不再各自硬编码魔法数字。MAX_TOTAL_LENGTH 与 worker c2c/config.py 的同名常量对齐。
MAX_TOTAL_LENGTH = 20          # 环肽总长上限 (aa)，total = len(core) + span_len
MIN_CORE_RATIO = 0.3           # 核心序列最小占比
SPAN_LEN_MIN, SPAN_LEN_MAX = 1, 15
NUM_SAMPLE_MIN, NUM_SAMPLE_MAX = 1, 100
NUM_MODELS_MIN, NUM_MODELS_MAX = 1, 5
TEMPERATURE_MIN, TEMPERATURE_MAX = 0.1, 2.0
TOP_P_MIN, TOP_P_MAX = 0.1, 1.0

# 有效的氨基酸字母
VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")
VALID_AA_PATTERN = re.compile(r'^[ACDEFGHIKLMNPQRSTVWY]+$', re.IGNORECASE)

# 有效的模型类型
VALID_MODEL_TYPES = {
    "alphafold2", "alphafold2_ptm",
    "alphafold2_multimer_v1", "alphafold2_multimer_v2", "alphafold2_multimer_v3",
    "deepfold_v1"
}

# 有效的 MSA 模式
VALID_MSA_MODES = {"single_sequence", "mmseqs2_uniref", "mmseqs2_uniref_env"}


# ==== 辅助函数 ====

def _get_current_user(request: Request):
    """获取当前认证用户"""
    if not hasattr(request.state, 'user') or not request.state.user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return request.state.user


def _validate_highfold_request(req: HighFoldC2CRequest):
    """验证 HighFold-C2C 请求参数"""
    # 1. core_sequence 必填
    if not req.core_sequence or not req.core_sequence.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error": "empty_core_sequence",
                "message": "核心肽段序列不能为空",
                "details": {"suggestion": "请输入核心肽段序列，如 NNN、CNNNC"}
            }
        )

    core = req.core_sequence.strip().upper()

    # 2. 只允许标准氨基酸
    if not VALID_AA_PATTERN.match(core):
        invalid_chars = [c for c in core if c not in VALID_AA]
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_amino_acids",
                "message": f"序列包含无效字符: {', '.join(set(invalid_chars))}",
                "details": {
                    "valid_amino_acids": "A, C, D, E, F, G, H, I, K, L, M, N, P, Q, R, S, T, V, W, Y",
                    "invalid_characters": list(set(invalid_chars))
                }
            }
        )

    # 3. 总长度限制
    # 真实环肽长度 = 核心序列 + 单侧延伸 span_len（C2C 只在 core 一侧追加 span_len 个残基，
    # 见 HighFold_C2C/c2c/generate.py: `core + span`），与 worker 的 MAX_TOTAL_LENGTH 校验一致。
    total_length = len(core) + req.span_len
    if total_length > MAX_TOTAL_LENGTH:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "total_length_exceeded",
                "message": f"总环肽长度 ({total_length} aa) 超过上限 {MAX_TOTAL_LENGTH}。请缩短核心序列或减小延伸长度。",
                "details": {
                    "core_length": len(core),
                    "span_len": req.span_len,
                    "total_length": total_length,
                    "max_total_length": MAX_TOTAL_LENGTH
                }
            }
        )

    # 4. 核心比例检查
    core_ratio = len(core) / total_length
    if core_ratio < MIN_CORE_RATIO:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "core_ratio_too_low",
                "message": f"核心序列占比 ({core_ratio * 100:.0f}%) 低于 {MIN_CORE_RATIO * 100:.0f}%。请增加核心长度或减小延伸长度。",
                "details": {
                    "core_length": len(core),
                    "total_length": total_length,
                    "core_ratio": round(core_ratio, 3),
                    "min_core_ratio": MIN_CORE_RATIO
                }
            }
        )

    # 5. span_len 范围
    if req.span_len < SPAN_LEN_MIN or req.span_len > SPAN_LEN_MAX:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_span_len",
                "message": f"延伸长度应在 {SPAN_LEN_MIN}~{SPAN_LEN_MAX} 之间，当前值: {req.span_len}",
                "details": {"min": SPAN_LEN_MIN, "max": SPAN_LEN_MAX}
            }
        )

    # 6. num_sample 范围
    if req.num_sample < NUM_SAMPLE_MIN or req.num_sample > NUM_SAMPLE_MAX:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_num_sample",
                "message": f"采样数量应在 {NUM_SAMPLE_MIN}~{NUM_SAMPLE_MAX} 之间，当前值: {req.num_sample}",
                "details": {"min": NUM_SAMPLE_MIN, "max": NUM_SAMPLE_MAX}
            }
        )

    # 7. model_type 枚举
    if req.model_type not in VALID_MODEL_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_model_type",
                "message": f"无效的模型类型: {req.model_type}",
                "details": {"valid_values": sorted(VALID_MODEL_TYPES)}
            }
        )

    # 8. msa_mode 枚举
    if req.msa_mode not in VALID_MSA_MODES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_msa_mode",
                "message": f"无效的 MSA 模式: {req.msa_mode}",
                "details": {"valid_values": sorted(VALID_MSA_MODES)}
            }
        )

    # 9. num_models 范围
    if req.num_models < NUM_MODELS_MIN or req.num_models > NUM_MODELS_MAX:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_num_models",
                "message": f"预测模型数量应在 {NUM_MODELS_MIN}~{NUM_MODELS_MAX} 之间，当前值: {req.num_models}",
                "details": {"min": NUM_MODELS_MIN, "max": NUM_MODELS_MAX}
            }
        )

    # 10. temperature 范围
    if req.temperature < TEMPERATURE_MIN or req.temperature > TEMPERATURE_MAX:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_temperature",
                "message": f"采样温度应在 {TEMPERATURE_MIN}~{TEMPERATURE_MAX} 之间，当前值: {req.temperature}",
                "details": {"min": TEMPERATURE_MIN, "max": TEMPERATURE_MAX}
            }
        )

    # 11. top_p 范围
    if req.top_p < TOP_P_MIN or req.top_p > TOP_P_MAX:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_top_p",
                "message": f"核采样阈值应在 {TOP_P_MIN}~{TOP_P_MAX} 之间，当前值: {req.top_p}",
                "details": {"min": TOP_P_MIN, "max": TOP_P_MAX}
            }
        )


# ==== 参数约束接口 ====
# 注意：必须在 GET /{task_id} 之前注册，否则会被路径参数路由吞掉。

@router.get("/constraints",
            summary="获取 HighFold-C2C 参数约束",
            description="返回后端权威的参数取值范围与枚举，供前端预校验回显，避免前后端魔法数字漂移。")
async def get_highfold_constraints():
    """HighFold-C2C 提交参数的约束（单一来源，与 _validate_highfold_request 共用常量）。"""
    return {
        "max_total_length": MAX_TOTAL_LENGTH,
        "min_core_ratio": MIN_CORE_RATIO,
        "span_len": {"min": SPAN_LEN_MIN, "max": SPAN_LEN_MAX},
        "num_sample": {"min": NUM_SAMPLE_MIN, "max": NUM_SAMPLE_MAX},
        "num_models": {"min": NUM_MODELS_MIN, "max": NUM_MODELS_MAX},
        "temperature": {"min": TEMPERATURE_MIN, "max": TEMPERATURE_MAX},
        "top_p": {"min": TOP_P_MIN, "max": TOP_P_MAX},
        "valid_amino_acids": sorted(VALID_AA),
        "valid_model_types": sorted(VALID_MODEL_TYPES),
        "valid_msa_modes": sorted(VALID_MSA_MODES),
    }


# ==== 任务创建接口 ====

@router.post("/predict",
             summary="创建 HighFold-C2C 环肽设计任务",
             description="提交环肽设计与结构预测任务。包含三个阶段：C2C 序列生成、HighFold 结构预测、理化性质评估。")
async def create_highfold_task(request: Request, highfold_request: HighFoldC2CRequest):
    """
    创建 HighFold-C2C 环肽设计任务。

    流程：
    1. 验证请求参数（序列格式、长度约束、核心比例等）
    2. 生成任务存储路径并上传 input.json 到 SeaweedFS
    3. 在 tasks 表创建任务记录 (task_type='highfold_c2c')
    4. 在 highfold_task_params 表写入任务参数
    5. HighFold-C2C 微服务将自动轮询处理此任务

    必填参数：core_sequence
    基础参数：span_len (默认5), num_sample (默认20), disulfide_bond_pairs (可选)
    高级参数：temperature, top_p, seed, model_type, msa_mode, num_models 等
    """
    current_user = _get_current_user(request)

    logger.info("User %s (user_id: %s) submitting HighFold-C2C task: "
                "core=%s, span_len=%d, num_sample=%d, model_type=%s",
                current_user.username, current_user.id,
                highfold_request.core_sequence, highfold_request.span_len,
                highfold_request.num_sample, highfold_request.model_type)

    try:
        # —— 1) 验证参数 —— #
        _validate_highfold_request(highfold_request)
        core = highfold_request.core_sequence.strip().upper()

        # —— 2) 创建任务存储路径 —— #
        job_id = str(uuid.uuid4())
        job_prefix = f"jobs/highfold_c2c/{job_id}"

        # 准备 input.json（供 HighFold-C2C 微服务读取）
        input_config = {
            "core_sequence": core,
            "span_len": highfold_request.span_len,
            "num_sample": highfold_request.num_sample,
            "temperature": highfold_request.temperature,
            "top_p": highfold_request.top_p,
            "seed": highfold_request.seed,
            "model_type": highfold_request.model_type,
            "msa_mode": highfold_request.msa_mode,
            "disulfide_bond_pairs": highfold_request.disulfide_bond_pairs,
            "num_models": highfold_request.num_models,
            "num_recycle": highfold_request.num_recycle,
            "use_templates": highfold_request.use_templates,
            "amber": highfold_request.amber,
            "num_relax": highfold_request.num_relax,
        }

        # 上传 input.json 到 SeaweedFS
        storage = get_storage()
        input_json_key = f"{job_prefix}/input/input.json"
        input_json_bytes = json.dumps(input_config, indent=2).encode('utf-8')
        await storage.upload_bytes(input_json_bytes, input_json_key, content_type="application/json")
        logger.info("Input config uploaded to: %s", input_json_key)

        # —— 3) 在 tasks 表创建任务记录 —— #
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="highfold_c2c",
            job_dir=job_prefix
        )

        # —— 4) 在 highfold_task_params 表写入参数 —— #
        try:
            HighFoldTaskParamsService.create_task_params(
                task_id=task_id,
                core_sequence=core,
                span_len=highfold_request.span_len,
                num_sample=highfold_request.num_sample,
                temperature=highfold_request.temperature,
                top_p=highfold_request.top_p,
                seed=highfold_request.seed,
                model_type=highfold_request.model_type,
                msa_mode=highfold_request.msa_mode,
                disulfide_bond_pairs=highfold_request.disulfide_bond_pairs,
                num_models=highfold_request.num_models,
                num_recycle=highfold_request.num_recycle,
                use_templates=highfold_request.use_templates,
                amber=highfold_request.amber,
                num_relax=highfold_request.num_relax,
            )
            logger.info("HighFold-C2C task params created for task %s", task_id)
        except Exception as e:
            logger.error("Failed to create HighFold-C2C task params for task %s: %s", task_id, e)
            # 参数记录失败不影响任务执行（worker 也会从 input.json 读取）

        # —— 5) 返回响应 —— #
        total_length = len(core) + highfold_request.span_len
        response_data = {
            "task_id": task_id,
            "status": "submitted",
            "message": "HighFold-C2C 环肽设计任务已成功提交",
            "details": {
                "job_id": job_id,
                "storage_prefix": job_prefix,
                "core_sequence": core,
                "total_peptide_length": total_length,
                "core_ratio": round(len(core) / total_length, 3),
                "parameters": {
                    "span_len": highfold_request.span_len,
                    "num_sample": highfold_request.num_sample,
                    "temperature": highfold_request.temperature,
                    "top_p": highfold_request.top_p,
                    "seed": highfold_request.seed,
                    "model_type": highfold_request.model_type,
                    "msa_mode": highfold_request.msa_mode,
                    "disulfide_bond_pairs": highfold_request.disulfide_bond_pairs,
                    "num_models": highfold_request.num_models,
                    "num_recycle": highfold_request.num_recycle,
                    "use_templates": highfold_request.use_templates,
                    "amber": highfold_request.amber,
                    "num_relax": highfold_request.num_relax,
                }
            },
            "next_steps": {
                "check_status": f"/highfold/{task_id}",
                "get_params": f"/highfold/{task_id}/params",
                "get_results": f"/highfold/{task_id}/results",
                "get_sequences": f"/highfold/{task_id}/sequences",
                "list_structures": f"/highfold/{task_id}/structures",
                "download_all": f"/highfold/{task_id}/download"
            }
        }

        return JSONResponse(content=response_data, status_code=201)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("HighFold-C2C task submission failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_server_error",
                "message": "HighFold-C2C 任务提交失败",
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
            summary="查询 HighFold-C2C 任务状态",
            description="获取指定 HighFold-C2C 任务的状态和基本信息")
async def get_highfold_task_status(request: Request, task_id: str):
    """查询 HighFold-C2C 任务的状态"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task)

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
        logger.error("Error fetching HighFold-C2C task %s for user %s: %s",
                     task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")


@router.get("/{task_id}/params",
            summary="查询 HighFold-C2C 任务参数",
            description="获取 HighFold-C2C 任务的配置参数详情")
async def get_highfold_task_params(request: Request, task_id: str):
    """查询 HighFold-C2C 任务的配置参数"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task)

        params = HighFoldTaskParamsService.get_task_params(task_id)
        return {"task_id": task_id, **highfold_results.build_public_params(params)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching HighFold-C2C task params %s for user %s: %s",
                     task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task parameters")


# ==== 结果查询接口 ====

@router.get("/{task_id}/results",
            summary="获取 HighFold-C2C 结果摘要",
            description="解析 output.csv 返回环肽评估结果的 JSON 数组")
async def get_highfold_results(request: Request, task_id: str):
    """
    获取 HighFold-C2C 任务的评估结果。

    解析 output/output.csv 文件，返回每条环肽的：
    Index, Cyclic sequence, pLDDT, Molecular weight, Isoelectric point,
    Aromaticity, Instability index, Hydrophobicity, Hydrophilicity
    """
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task, require_finished=True)
        return await highfold_results.fetch_results_parsed(task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching HighFold-C2C results for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to fetch results")


@router.get("/{task_id}/results/csv",
            summary="下载 HighFold-C2C 结果 CSV",
            description="下载原始 output.csv 文件")
async def download_highfold_results_csv(request: Request, task_id: str):
    """下载 HighFold-C2C 评估结果的原始 CSV 文件"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task, require_finished=True)
        content = await highfold_results.fetch_results_csv_bytes(task)

        return StreamingResponse(
            io.BytesIO(content),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=highfold_results_{task_id[:8]}.csv",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading HighFold-C2C CSV for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to download CSV")


@router.get("/{task_id}/sequences",
            summary="获取 FASTA 序列",
            description="解析 predict.fasta 返回生成的环肽序列列表")
async def get_highfold_sequences(request: Request, task_id: str):
    """获取 C2C 生成的环肽序列（FASTA 格式解析为 JSON）"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task, require_finished=True)
        return await highfold_results.fetch_sequences(task)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching HighFold-C2C sequences for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to fetch sequences")


@router.get("/{task_id}/structures",
            summary="列出 PDB 结构文件",
            description="列出 HighFold 预测生成的所有 PDB 结构文件")
async def list_highfold_structures(request: Request, task_id: str):
    """列出 HighFold 结构预测输出的 PDB 文件"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task, require_finished=True)
        return await highfold_results.list_structures(
            task,
            download_url_prefix=f"/highfold/{task_id}/structures",
            share_url_base=_public_viewer_base(request),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing HighFold-C2C structures for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to list structures")


@router.get("/{task_id}/structures/{filename}",
            summary="下载单个 PDB 文件",
            description="下载指定的 PDB 结构文件")
async def download_highfold_structure(request: Request, task_id: str, filename: str):
    """下载 HighFold 预测的单个 PDB 结构文件"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task, require_finished=True)

        # 安全检查
        if '..' in filename or '/' in filename or not re.match(r'^[\w\-.]+$', filename):
            raise HTTPException(status_code=400, detail="Invalid filename")
        if not filename.endswith('.pdb'):
            raise HTTPException(status_code=400, detail="Only PDB files can be downloaded via this endpoint")

        content = await highfold_results.fetch_structure_pdb_bytes(task, filename)

        return StreamingResponse(
            io.BytesIO(content),
            media_type="chemical/x-pdb",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading HighFold-C2C structure %s for task %s: %s",
                     filename, task_id, e)
        raise HTTPException(status_code=500, detail="Failed to download structure file")


@router.get("/{task_id}/download",
            summary="打包下载所有输出",
            description="将 HighFold-C2C 任务的所有输出文件打包为 ZIP 下载")
async def download_highfold_all(request: Request, task_id: str):
    """将 HighFold-C2C 所有输出文件打包为 ZIP 下载"""
    current_user = _get_current_user(request)

    try:
        task = TaskService.get_task(task_id)

        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        highfold_results.ensure_highfold_task(task, require_finished=True)

        zip_bytes = await highfold_results.build_results_zip(task)
        filename = f"highfold_c2c_results_{task_id[:8]}.zip"

        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading HighFold-C2C results for task %s: %s", task_id, e)
        raise HTTPException(status_code=500, detail="Failed to download result files")
