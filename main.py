import time
import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import pandas as pd
from fastapi.responses import JSONResponse

from rdkit import Chem
from rdkit.Chem import Descriptors, QED, Draw
from io import BytesIO
from PIL import Image
import io
from Vina.vina_workflow import vina_docking_from_list

# 你的其他 imports 保持不变 … 
from fragment_processor import fragmentize_molecule
from generate import GenerateRunner
from dataset import Dataset
from combine_mol import connect_constVar_try
import sascorer
import torch
import sys
import json
ROOT = Path(__file__).resolve().parent
VINA_DIR = ROOT / "Vina"
if str(VINA_DIR) not in sys.path:
    sys.path.insert(0, str(VINA_DIR))
app = FastAPI()

# ============================================
# 1. 为 docking 定义 Pydantic 模型
# ============================================
class DockingLigand(BaseModel):
    smiles: str
    title: str

class DockingRequest(BaseModel):
    ligands: List[DockingLigand]
    min_ph: Optional[float] = 6.0
    max_ph: Optional[float] = 8.0
    n_jobs: Optional[int]   = 10

# -------------- 你的其他模型定义（Fragment / GenerateRequest / MoleculeOutput）保持不变 --------------

class Fragment(BaseModel):
    variable_smiles: str
    constant_smiles: str
    record_id: str
    normalized_smiles: str
    attachment_order: int

class FragmentResponse(BaseModel):
    fragments: List[Fragment]

class GenerateRequest(BaseModel):
    constSmiles: str
    varSmiles: str
    mainCls: str
    minorCls: str
    deltaValue: str
    num: int

class MoleculeOutput(BaseModel):
    smile: str
    molwt: float
    tpsa: float
    slogp: float
    sa: float
    qed: float

class Options:
    def __init__(self, **entries):
        self.__dict__.update(entries)

# ============================================
# 2. 一些已有的工具函数（calculate_descriptors, run_generate_runner 等）
# ============================================
def calculate_descriptors(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    
    molwt = round(Descriptors.MolWt(mol), 1)
    tpsa = round(Descriptors.TPSA(mol), 1)
    slogp = round(Descriptors.MolLogP(mol), 1)
    sa    = round(sascorer.calculateScore(mol), 1)
    qed_v = round(QED.qed(mol), 1)

    # 检查除法前是否为 0
    some_ratio = None
    if tpsa != 0:
        some_ratio = molwt / tpsa

    return {"molwt": molwt, "tpsa": tpsa, "slogp": slogp, "sa": sa, "qed": qed_v}

def run_generate_runner(const_smiles, var_smiles, main_cls, minor_cls, delta_value, num_samples):
    opt = {
        'batch_size': num_samples,
        'data_path' :  './',
        'decode_type' :  'multinomial',
        'dev_no' :  0,
        'epoch' :  20,
        'model_choice' :  'transformer',
        'model_path' :  './raw_pretrain_frag/checkpoint',
        'num_samples' :  50,
        'overwrite' :  True,
        'test_file_name' :  'test_cut',
        'vocab_path' :  './'
    }
    opt = Options(**opt)
    runner = GenerateRunner(opt)

    data = {
        "constantSMILES": const_smiles,
        "fromVarSMILES": var_smiles,
        "main_cls": main_cls,
        "minor_cls": minor_cls,
        "Delta_Value": delta_value
    }
    test_data = pd.DataFrame([data])
    dataset = Dataset(test_data, vocabulary=runner.vocab, tokenizer=runner.tokenizer, prediction_mode=True)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=num_samples, shuffle=False, collate_fn=Dataset.collate_fn)
    result = []

    for batch in dataloader:
        src, source_length, _, src_mask, _, _, df = batch
        src = src.to(runner.device)
        src_mask = src_mask.to(runner.device)
        source_length = source_length.to(runner.device)
        smiles_list = runner.sample(
            model_choice="transformer", 
            model=runner.model, 
            src=src, 
            src_mask=src_mask, 
            source_length=source_length, 
            decode_type="multinomial", 
            num_samples=num_samples
        )
        for smiles_group in smiles_list:
            for smile in smiles_group:
                newsmile = connect_constVar_try(const_smiles, smile)
                descriptors = calculate_descriptors(newsmile)
                if descriptors:
                    result.append({
                        "smile": newsmile,
                        "molwt": descriptors['molwt'],
                        "tpsa": descriptors['tpsa'],
                        "slogp": descriptors['slogp'],
                        "sa": descriptors['sa'],
                        "qed": descriptors['qed']
                    })
    return result

# ============================================
# 3. 已有的 /smiles2img, /fragmentize, /generate 接口 保持不变
# ============================================
@app.get("/smiles2img")
async def smiles2img(smiles: str = Query(..., description="SMILES string of the molecule")):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": "Invalid SMILES string"}

    drawer = Draw.MolDraw2DCairo(200, 200)
    drawer.SetFontSize(1.0)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()

    pil_image = Image.open(io.BytesIO(drawer.GetDrawingText()))
    strIO = BytesIO()
    pil_image.save(strIO, "PNG")
    strIO.seek(0)
    return StreamingResponse(strIO, media_type="image/png")

@app.get("/fragmentize", response_model=FragmentResponse)
async def fragmentize(smiles: str = Query(..., description="SMILES string of the molecule")):
    try:
        fragment_df = fragmentize_molecule(smiles)
        fragments = fragment_df.to_dict(orient="records")
        return FragmentResponse(fragments=fragments)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"发生错误: {str(e)}")


@app.post("/generate", response_model=List[MoleculeOutput])
async def generate_molecules(request: GenerateRequest):
    """
    1. 先将请求参数保存到 jobs/<job_id>/input.json
    2. 执行 run_generate_runner 生成结果
    3. 将结果保存到 jobs/<job_id>/output.json
    4. 返回结果给调用者
    """
    # （1）生成一个唯一的 job_id，并创建对应文件夹
    try:
        JOBS_DIR = ROOT / "jobs"
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


# ============================================
# 4. 新增 /docking 接口：接受 Ligand 列表 以及 min_ph, max_ph, n_jobs
# ============================================
# ────────────────────────────────────────────────────────────────────
#  修改后的 /docking 接口：直接传递 ligands 列表，不再手动写临时 CSV
# ────────────────────────────────────────────────────────────────────
@app.post("/docking")
async def docking_endpoint(request: DockingRequest):
    """
    接收 JSON：
    {
      "ligands": [
         {"smiles": "...", "title": "..."},
         ...
      ],
      "min_ph": 6.0,
      "max_ph": 8.0,
      "n_jobs": 10
    }
    直接调用 vina_docking_from_list，返回 run_id 和结果列表。
    """
    try:
        # 1. 直接将 request.ligands 传给 vina_docking_from_list
        receptor_path = str(Path("/home/davis/projects/dockingVina/resource") / "protein_7UDP.pdbqt")

        run_dir = vina_docking_from_list(
            ligands=[lig.dict() for lig in request.ligands],
            receptor_pdbqt=receptor_path,
            min_ph=request.min_ph,
            max_ph=request.max_ph,
            n_jobs=request.n_jobs
        )
        # run_dir 示例： "/home/davis/projects/dockingVina/resource/<uuid>"

        # 2. 读取 run_dir/dockRes.csv，把它转成 JSON
        result_csv = Path(run_dir) / "dockRes.csv"
        if not result_csv.exists():
            raise HTTPException(status_code=500, detail="docking 过程中未生成 dockRes.csv")

        df_result = pd.read_csv(result_csv)
        json_result = df_result.to_dict(orient="records")

        # 3. 返回 JSON
        #    run_id 取 run_dir 的最后一段目录名
        run_id = Path(run_dir).name
        return JSONResponse(content={"run_id": run_id, "results": json_result})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"docking 失败: {str(e)}")