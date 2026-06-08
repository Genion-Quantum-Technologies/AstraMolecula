"""
HighFold-C2C 结果读取共享服务

封装 SeaweedFS 上结果文件的读取与解析逻辑，供 authenticated 路由
(`/highfold/...`) 与公开路由 (`/public/highfold/...`) 共享调用，
避免重复实现导致两端行为漂移。

约定：
- 调用方负责调用 `ensure_highfold_task` 校验 task 类型与归属
- 调用方负责按需校验 `task.status == "finished"`
- 本模块不抛认证/授权错误，只对结果不存在/解析失败抛 HTTPException
"""
import csv
import io
import json
import zipfile
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from fastapi import HTTPException

from astra_molecula.services.storage import get_storage

HIGHFOLD_TASK_TYPE = "highfold_c2c"


def normalize_storage_prefix(job_dir: str) -> str:
    """标准化 job_dir 为 SeaweedFS 存储前缀"""
    if not job_dir:
        return job_dir
    if job_dir.startswith('/'):
        if '/jobs/' in job_dir:
            idx = job_dir.index('/jobs/') + 1
            return job_dir[idx:]
    return job_dir


def ensure_highfold_task(task, *, require_finished: bool = False) -> None:
    """统一校验：task 必须存在、类型为 highfold_c2c，可选要求 finished。"""
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.task_type != HIGHFOLD_TASK_TYPE:
        raise HTTPException(status_code=400, detail="Task is not a HighFold-C2C task")
    if require_finished and task.status != "finished":
        raise HTTPException(
            status_code=409,
            detail={
                "error": "task_not_finished",
                "message": f"任务状态为 {task.status}，尚未完成",
                "details": {"current_status": task.status},
            },
        )


# ---- 结果读取 ----

async def fetch_results_csv_bytes(task) -> bytes:
    """读取原始 output.csv 字节内容"""
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    csv_key = f"{storage_prefix}/output/output.csv"
    if not await storage.file_exists(csv_key):
        raise HTTPException(status_code=404, detail="Results CSV not found")
    return await storage.download_bytes(csv_key)


async def fetch_results_parsed(task) -> Dict[str, Any]:
    """读取 output.csv 并解析为 JSON 行列表（数值字段尝试转 float）"""
    content = await fetch_results_csv_bytes(task)
    text = content.decode('utf-8')

    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for row in reader:
        parsed_row = {}
        for key, value in row.items():
            try:
                parsed_row[key] = float(value)
            except (ValueError, TypeError):
                parsed_row[key] = value
        rows.append(parsed_row)

    return {
        "task_id": task.id,
        "total_sequences": len(rows),
        "results": rows,
    }


async def fetch_sequences(task) -> Dict[str, Any]:
    """读取 predict.fasta 并解析为 [{name, sequence}, ...]"""
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    fasta_key = f"{storage_prefix}/output/predict.fasta"

    if not await storage.file_exists(fasta_key):
        raise HTTPException(status_code=404, detail="FASTA file not found")

    content = await storage.download_bytes(fasta_key)
    text = content.decode('utf-8')

    sequences: List[Dict[str, str]] = []
    current_name: Optional[str] = None
    current_seq: List[str] = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if line.startswith('>'):
            if current_name is not None:
                sequences.append({"name": current_name, "sequence": ''.join(current_seq)})
            current_name = line[1:].strip()
            current_seq = []
        else:
            current_seq.append(line)
    if current_name is not None:
        sequences.append({"name": current_name, "sequence": ''.join(current_seq)})

    return {
        "task_id": task.id,
        "total_sequences": len(sequences),
        "sequences": sequences,
    }


async def list_structures(
    task,
    *,
    download_url_prefix: str,
    share_url_base: Optional[str] = None,
) -> Dict[str, Any]:
    """列出 output 目录下的所有 .pdb 文件

    download_url_prefix: 用于拼接前端可访问的下载链接，例如：
      - "/highfold/{task_id}/structures"
      - "/public/highfold/{task_id}/structures"

    share_url_base: 公开 3D 查看页基础地址（不含 query），用于为每个结构生成
      可直接打开 3D 视图的分享链接，镜像 docking 的 share_url 落地方式，例如：
      - "https://<host>/public/highfold-viewer"
      最终拼成 "{share_url_base}?taskId={task_id}&filename={filename}"。
      传 None 时不输出 share_url 字段。
    """
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    output_prefix = f"{storage_prefix}/output/"

    all_files = await storage.list_files_recursive(output_prefix)

    pdb_files = []
    for file_key in all_files:
        if file_key.endswith('.pdb'):
            filename = file_key.split('/')[-1]
            file_info = await storage.get_file_info(file_key)
            entry = {
                "filename": filename,
                "storage_key": file_key,
                "size": file_info.get("size") if file_info else None,
                "download_url": f"{download_url_prefix}/{filename}",
            }
            if share_url_base:
                entry["share_url"] = (
                    f"{share_url_base}?taskId={task.id}&filename={quote(filename)}"
                )
            pdb_files.append(entry)

    return {
        "task_id": task.id,
        "total_structures": len(pdb_files),
        "structures": pdb_files,
    }


async def fetch_structure_pdb_bytes(task, filename: str) -> bytes:
    """读取单个 PDB 文件字节内容；调用方负责 filename 安全校验"""
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    remote_key = f"{storage_prefix}/output/{filename}"

    if not await storage.file_exists(remote_key):
        raise HTTPException(status_code=404, detail=f"Structure file not found: {filename}")

    return await storage.download_bytes(remote_key)


async def build_results_zip(task) -> bytes:
    """将 output 目录所有文件打包为 ZIP，返回字节"""
    storage = get_storage()
    storage_prefix = normalize_storage_prefix(task.job_dir)
    output_prefix = f"{storage_prefix}/output/"

    files = await storage.list_files_recursive(output_prefix)

    if not files:
        raise HTTPException(status_code=404, detail="No output files found")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_key in files:
            if file_key.endswith('/'):
                continue
            try:
                content = await storage.download_bytes(file_key)
                if file_key.startswith(output_prefix):
                    arcname = file_key[len(output_prefix):]
                else:
                    arcname = file_key.split('output/')[-1]
                zf.writestr(arcname, content)
            except Exception:
                # 单个文件失败不影响整体打包；调用方层有日志
                continue

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# ---- 参数与元数据 ----

def build_public_task_info(task) -> Dict[str, Any]:
    """构造公开任务元数据（不含 user_id 等敏感字段）"""
    return {
        "task_id": task.id,
        "task_type": task.task_type,
        "status": task.status,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
    }


def build_public_params(params) -> Dict[str, Any]:
    """从 HighFoldTaskParams ORM 对象构造公开参数 dict（已剔除 task_id 关联的敏感信息）"""
    if not params:
        raise HTTPException(status_code=404, detail="HighFold-C2C task parameters not found")

    total_length = (
        len(params.core_sequence) + params.span_len * 2
        if params.core_sequence else None
    )

    return {
        "core_sequence": params.core_sequence,
        "span_len": params.span_len,
        "num_sample": params.num_sample,
        "total_peptide_length": total_length,
        "temperature": float(params.temperature),
        "top_p": float(params.top_p),
        "seed": params.seed,
        "model_type": params.model_type,
        "msa_mode": params.msa_mode,
        "disulfide_bond_pairs": params.disulfide_bond_pairs,
        "num_models": params.num_models,
        "num_recycle": params.num_recycle,
        "use_templates": params.use_templates,
        "amber": params.amber,
        "num_relax": params.num_relax,
    }
