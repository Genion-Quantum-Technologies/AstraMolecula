import io
import json
import time
from tkinter import Image
from typing import List
import uuid
from fastapi.responses import StreamingResponse
from rdkit import Chem
from rdkit.Chem import Draw
from fastapi import APIRouter, HTTPException, Query

from config import ROOT
from utils.fragment_processor import fragmentize_molecule
from utils.tools import FragmentResponse, GenerateRequest, MoleculeOutput, run_generate_runner

router = APIRouter(tags=["Smiles"])

@router.get("/smiles2img")
async def smiles2img(smiles: str = Query(..., description="SMILES string of the molecule")):
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
    try:
        fragment_df = fragmentize_molecule(smiles)
        fragments = fragment_df.to_dict(orient="records")
        return FragmentResponse(fragments=fragments)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发生错误: {str(e)}")


@router.post("/generate", response_model=List[MoleculeOutput])
async def generate_molecules(request: GenerateRequest):
    """
    1. 先将请求参数保存到 jobs/<job_id>/input.json
    2. 执行 run_generate_runner 生成结果
    3. 将结果保存到 jobs/<job_id>/output.json
    4. 返回结果给调用者
    """
    # （1）生成一个唯一的 job_id，并创建对应文件夹
    try:
        JOBS_DIR = ROOT / "jobs/generate"
        JOBS_DIR.mkdir(exist_ok=True)

        job_id = uuid.uuid4().hex
        job_dir = JOBS_DIR / job_id
        job_dir.mkdir()

        # （2）将请求体内容保存到 job_dir/input.json
        input_data = request.model_dump()
        with open(job_dir / "input.json", "w", encoding="utf-8") as f_in:
            json.dump(input_data, f_in, indent=2, ensure_ascii=False)

        # （3）启动生成逻辑
        start_time = time.time()
        result = run_generate_runner(
            request.constSmiles,
            request.varSmiles,
            request.mainCls,
            request.minorCls,
            request.deltaValue,
            request.num
        )
        end_time = time.time()

        # （4）将生成结果写入 job_dir/output.json
        with open(job_dir / "output.json", "w", encoding="utf-8") as f_out:
            json.dump(result, f_out, indent=2, ensure_ascii=False)

        # （5）可以记录耗时
        duration = end_time - start_time
        # 你也可以将耗时写入一份 log.txt
        with open(job_dir / "log.txt", "w", encoding="utf-8") as log_f:
            log_f.write(f"Started at: {time.ctime(start_time)}\n")
            log_f.write(f"Finished at: {time.ctime(end_time)}\n")
            log_f.write(f"Duration: {duration:.2f} seconds\n")

        # （6）把结果返回给调用者
        return result

    except Exception as e:
        # 捕获异常并记录详细的错误信息，包括堆栈追踪
        error_message = f"Error occurred: {str(e)}"
        print(error_message)  # 打印到控制台，或者使用 logging 模块记录到日志文件
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")