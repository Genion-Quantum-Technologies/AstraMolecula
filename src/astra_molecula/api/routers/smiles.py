import io
import json
import logging
from PIL import Image
import uuid
from fastapi.responses import StreamingResponse
from rdkit import Chem
from rdkit.Chem import Draw
from fastapi import APIRouter, HTTPException, Query, Request

from astra_molecula.db.services.task_service import TaskService
from astra_molecula.schemas.requests.basic_request import GenerateRequestList
from astra_molecula.schemas.responses.basic_response import FragmentResponse
from astra_molecula.utils.fragment_processor import fragmentize_molecule
from astra_molecula.core.config import ROOT
from astra_molecula.services.storage import get_storage

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
    1. 将请求参数保存到 SeaweedFS
    2. 创建一条待处理的 generate 任务记录
    3. 由 task_worker 在后台读取任务并生成结果
    """
    # 从中间件注入的 state 中取出已验证的用户
    current_user = request.state.user
    logger.info("User %s submit generate task", current_user.username)

    try:
        # （1）生成一个唯一的 job_id
        job_id = str(uuid.uuid4())
        
        # 构建 SeaweedFS 存储路径（不再创建本地目录）
        storage_prefix = f"jobs/generate/{job_id}"
        
        # （2）将请求体内容保存到 SeaweedFS
        storage = get_storage()
        input_data = generate_requests.model_dump()
        input_json_bytes = json.dumps(input_data, indent=2, ensure_ascii=False).encode('utf-8')
        
        # 上传到 SeaweedFS
        remote_key = f"{storage_prefix}/input.json"
        await storage.upload_bytes(input_json_bytes, remote_key, content_type="application/json")
        logger.info("Uploaded input.json to SeaweedFS: %s", remote_key)

        # （3）创建任务，job_dir 存储为逻辑路径（用于后续查找）
        task_id = TaskService.create_task(
            user_id=current_user.id,
            task_type="generate",
            job_dir=storage_prefix  # 存储逻辑路径而非本地路径
        )

        # （3.5）—— 这里以前是 `asyncio.create_task(task_processor.process_task(task))` ——
        #
        # ADR 0012 P3：`generate` 不再跑在 API 进程里。
        #
        # 它过去就在服务其它所有请求的那个 uvicorn worker 里做 PyTorch 前向。实测运行时间
        # 跨度是 **0.1 秒 ~ 50 分钟**，且**无法从请求预判**，所以一个病态输入就能把整个
        # AstraMolecula API 的 p99 拖死将近一小时。而且那个 Task 从不被 await、也不被持有 ——
        # pod 一重启，计算就丢了，数据库那行永远卡在 running。
        #
        # 现在：这里只 INSERT 一行 `pending`（上面已经做完了），compute-foundry operator
        # 会把它 reconcile 成一个 Argo Workflow —— 独立 pod、独立 CPU 配额，以及它从来
        # 没有过的 `activeDeadlineSeconds`。
        #
        # 后端到此为止。**不要**在这里把异步调用加回来。
        logger.info("Generate task %s queued; compute-foundry will reconcile it into a workflow", task_id)
            # 即使启动失败，也返回任务ID，让旧的轮询机制处理

        # （4）立即返回 task_id，让客户端稍后查询结果
        return {"task_id": task_id}

    except Exception as e:
        # 捕获异常并记录详细的错误信息，包括堆栈追踪
        error_message = f"Error occurred: {str(e)}"
        logger.exception("Generate molecules failed: %s", error_message)
        raise HTTPException(status_code=500, detail=error_message)
