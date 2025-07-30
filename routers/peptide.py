import os
import uuid
import shutil
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, Request, HTTPException, UploadFile, File
from database.services import TaskService
from requests.basic_request import PeptideOptimizationRequest
from responses.basic_response import TaskResponse
from utils.log import get_logger
from config import ROOT

logger = get_logger("peptide_router", str(ROOT / "logs" / "tasks.log"), isMain=True)

router = APIRouter(prefix="/peptide", tags=["Peptide Optimization"])

@router.post("/optimize", response_model=TaskResponse,
           summary="创建蛋白优化任务",
           description="提交蛋白优化任务到队列，peptide_opt服务会定时查询并处理")
async def create_optimization_task(request: Request, optimization_request: PeptideOptimizationRequest):
    """
    创建蛋白优化任务。
    
    需要提供：
    - peptide_sequence: 肽段序列
    - receptor_pdb_filename: 受体蛋白PDB文件名（需要先通过/uploads上传）
    - cores: CPU核心数（可选，默认12）
    - cleanup: 是否清理中间文件（可选，默认True）
    - step: 运行特定步骤（可选，None表示运行完整流程）
    - proteinmpnn_enabled: 是否启用ProteinMPNN优化（可选，默认True）
    """
    current_user = request.state.user
    logger.info("User %s creating peptide optimization task", current_user.username)
    
    try:
        # 验证输入参数
        if not optimization_request.peptide_sequence.strip():
            raise HTTPException(status_code=400, detail="Peptide sequence cannot be empty")
        
        if not optimization_request.receptor_pdb_filename:
            raise HTTPException(status_code=400, detail="Receptor PDB filename is required")
        
        if optimization_request.step and (optimization_request.step < 1 or optimization_request.step > 8):
            raise HTTPException(status_code=400, detail="Step must be between 1 and 8")
        
        # 检查上传的PDB文件是否存在
        uploads_dir = Path(ROOT) / "uploads" / current_user.id
        receptor_pdb_path = uploads_dir / optimization_request.receptor_pdb_filename
        
        if not receptor_pdb_path.exists():
            raise HTTPException(
                status_code=404, 
                detail=f"Receptor PDB file '{optimization_request.receptor_pdb_filename}' not found. Please upload it first."
            )
        
        # 创建任务目录
        task_id = uuid.uuid4().hex
        job_dir = Path(ROOT) / "jobs" / "peptide_optimization" / task_id
        job_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建input子目录
        input_dir = job_dir / "input"
        input_dir.mkdir(exist_ok=True)
        
        # 复制受体PDB文件到input目录，重命名为标准名称
        shutil.copy2(receptor_pdb_path, input_dir / "5ffg.pdb")
        
        # 创建peptide.fasta文件
        peptide_fasta_path = input_dir / "peptide.fasta"
        with open(peptide_fasta_path, 'w') as f:
            f.write(">peptide\n")
            f.write(optimization_request.peptide_sequence.strip() + "\n")
        
        # 创建参数配置文件
        config_path = job_dir / "optimization_config.txt"
        with open(config_path, 'w') as f:
            f.write(f"cores={optimization_request.cores}\n")
            f.write(f"cleanup={optimization_request.cleanup}\n")
            f.write(f"proteinmpnn_enabled={optimization_request.proteinmpnn_enabled}\n")
            if optimization_request.step:
                f.write(f"step={optimization_request.step}\n")
            f.write(f"peptide_sequence={optimization_request.peptide_sequence}\n")
            f.write(f"receptor_pdb_filename={optimization_request.receptor_pdb_filename}\n")
        
        # 在数据库中创建任务记录
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="peptide_optimization",
            job_dir=str(job_dir)
        )
        
        logger.info("Peptide optimization task created: task_id=%s, user=%s", 
                   task_id, current_user.username)
        
        # 获取创建的任务对象
        created_task = TaskService.get_task(task_id)
        if not created_task:
            raise HTTPException(status_code=500, detail="Failed to retrieve created task")
        
        return TaskResponse(
            id=created_task.id,
            user_id=created_task.user_id,
            task_type=created_task.task_type,
            status=created_task.status,
            job_dir=created_task.job_dir,
            created_at=created_task.created_at,
            finished_at=created_task.finished_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating peptide optimization task for user %s: %s", 
                    current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to create optimization task")


@router.get("/optimize/{task_id}", response_model=TaskResponse,
           summary="获取蛋白优化任务状态",
           description="查询特定蛋白优化任务的状态和详细信息")
async def get_optimization_task_status(request: Request, task_id: str):
    """
    获取蛋白优化任务的状态和详细信息。
    """
    current_user = request.state.user
    logger.info("User %s requesting peptide optimization task status: %s", 
               current_user.username, task_id)
    
    try:
        task = TaskService.get_task(task_id)
        
        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.task_type != "peptide_optimization":
            raise HTTPException(status_code=400, detail="Task is not a peptide optimization task")
        
        return task
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching peptide optimization task %s for user %s: %s", 
                    task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task status")


@router.get("/optimize/{task_id}/config",
           summary="获取蛋白优化任务配置",
           description="查询蛋白优化任务的配置参数")
async def get_optimization_task_config(request: Request, task_id: str) -> Dict[str, Any]:
    """
    获取蛋白优化任务的配置参数。
    """
    current_user = request.state.user
    
    try:
        task = TaskService.get_task(task_id)
        
        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task.task_type != "peptide_optimization":
            raise HTTPException(status_code=400, detail="Task is not a peptide optimization task")
        
        # 读取配置文件
        config_path = Path(task.job_dir) / "optimization_config.txt"
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Task configuration not found")
        
        config = {}
        with open(config_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    # 尝试转换数据类型
                    if value.lower() in ('true', 'false'):
                        config[key] = value.lower() == 'true'
                    elif value.isdigit():
                        config[key] = int(value)
                    else:
                        config[key] = value
        
        return config
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching peptide optimization task config %s for user %s: %s", 
                    task_id, current_user.username, e)
        raise HTTPException(status_code=500, detail="Failed to fetch task configuration")
