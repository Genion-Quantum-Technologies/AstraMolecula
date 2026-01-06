import io
import json
import logging
from PIL import Image
import uuid
from fastapi.responses import StreamingResponse
from rdkit import Chem
from rdkit.Chem import Draw
from fastapi import APIRouter, HTTPException, Query, Request

from database.services.task_service import TaskService
from requests.basic_request import GenerateRequestList
from responses.basic_response import FragmentResponse
from utils.fragment_processor import fragmentize_molecule
from config import ROOT

logger = logging.getLogger("smiles_router")

router = APIRouter(tags=["Smiles"])

@router.get("/smiles2img")
async def smiles2img(smiles: str = Query(..., description="SMILES string of the molecule")):
    logger.info("Convert SMILES to image: %s", smiles)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": "Invalid SMILES string"}

    drawer = Draw.MolDraw2DCairo(200, 200)
    drawer.SetFontSize(1.0)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()

    pil_image = Image.open(io.BytesIO(drawer.GetDrawingText()))
    strIO = io.BytesIO()
    pil_image.save(strIO, "PNG")
    strIO.seek(0)
    return StreamingResponse(strIO, media_type="image/png")

@router.get("/fragmentize", response_model=FragmentResponse)
async def fragmentize(smiles: str = Query(..., description="SMILES string of the molecule")):
    logger.info("Fragmentize molecule: %s", smiles)
    try:
        fragment_df = fragmentize_molecule(smiles)
        fragments = fragment_df.to_dict(orient="records")
        return FragmentResponse(fragments=fragments)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发生错误: {str(e)}")

@router.post("/generate")
async def generate_molecules(
    request: Request,
    generate_requests: GenerateRequestList
):
    """
    1. 将请求参数保存到 jobs/<job_id>/input.json
    2. 创建一条待处理的 generate 任务记录
    3. 由 task_worker 在后台读取任务并生成结果
    """
    # 从中间件注入的 state 中取出已验证的用户
    current_user = request.state.user
    logger.info("User %s submit generate task", current_user.username)

    try:
        # （1）生成一个唯一的 job_id，并创建对应文件夹
        JOBS_DIR = ROOT / "jobs" / "generate"
        JOBS_DIR.mkdir(parents=True, exist_ok=True)

        job_id = str(uuid.uuid4())
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir()

        # （2）将请求体内容保存到 job_dir/input.json
        input_data = generate_requests.model_dump()
        with open(job_dir / "input.json", "w", encoding="utf-8") as f_in:
            json.dump(input_data, f_in, indent=2, ensure_ascii=False)

        # （3）创建任务，供后台 worker 执行
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="generate",
            job_dir=str(job_dir)
        )

        # （3.5）启动异步处理 —— #
        try:
            from async_task_processor import task_processor
            task = TaskService.get_task(task_id)
            if task:
                # 在后台启动任务处理
                import asyncio
                asyncio.create_task(task_processor.process_task(task))
                logger.info("Started async processing for generate task %s", task_id)
            else:
                logger.error("Failed to retrieve created generate task %s", task_id)
        except Exception as e:
            logger.error("Failed to start async processing for generate task %s: %s", task_id, e)
            # 即使启动失败，也返回任务ID，让旧的轮询机制处理

        # （4）立即返回 task_id，让客户端稍后查询结果
        return {"task_id": task_id}

    except Exception as e:
        # 捕获异常并记录详细的错误信息，包括堆栈追踪
        error_message = f"Error occurred: {str(e)}"
        logger.exception("Generate molecules failed: %s", error_message)
        raise HTTPException(status_code=500, detail=error_message)
