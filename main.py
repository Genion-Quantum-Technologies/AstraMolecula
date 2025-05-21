import time
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import subprocess
from typing import List
from fragment_processor import fragmentize_molecule
from fastapi.responses import StreamingResponse
import torch
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, QED, Draw
from io import BytesIO
from PIL import Image
import io
from generate import GenerateRunner
from dataset import Dataset
from combine_mol import connect_constVar_try
import sascorer
app = FastAPI()


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

def calculate_descriptors(smiles):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    
    # molwt = Descriptors.MolWt(mol)
    # tpsa = Descriptors.TPSA(mol)
    # slogp = Descriptors.MolLogP(mol)
    # sa = sascorer.calculateScore(mol) 
    # qed = QED.qed(mol)
    molwt = round(Descriptors.MolWt(mol), 1)  # 保留 1 位小数
    tpsa = round(Descriptors.TPSA(mol), 1)
    slogp = round(Descriptors.MolLogP(mol), 1)
    sa = round(sascorer.calculateScore(mol), 1)
    qed = round(QED.qed(mol), 1)

    # 检查除法前是否为 0
    if tpsa == 0:
        print("Warning: TPSA is zero, skipping division.")
        some_ratio = None  
    else:
        some_ratio = molwt / tpsa  # 安全的除法操作
    
    return {"molwt": molwt, "tpsa": tpsa, "slogp": slogp, "sa": sa, "qed": qed}

def run_generate_runner(const_smiles, var_smiles, main_cls, minor_cls, delta_value, num_samples):
    # 初始化生成器的配置选项
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
        # 'save_directory' :  './demo_gen',
        'test_file_name' :  'test_cut',
        'vocab_path' :  './'
    }

    # 将 opt 字典转换为 Options 对象
    opt = Options(**opt)
    print("--------------opt---------------")
    print(opt)
    runner = GenerateRunner(opt)

    # 创建数据
    data = {
        "constantSMILES": const_smiles,
        "fromVarSMILES": var_smiles,
        "main_cls": main_cls,
        "minor_cls": minor_cls,
        "Delta_Value": delta_value
    }
    
    # 创建 Dataset 实例
    test_data = pd.DataFrame([data])
    dataset = Dataset(test_data, vocabulary=runner.vocab, tokenizer=runner.tokenizer, prediction_mode=True)

    # 生成 SMILES
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=num_samples, shuffle=False, collate_fn=Dataset.collate_fn)
    result = []

    for batch in dataloader:
        src, source_length, _, src_mask, _, _, df = batch
        src = src.to(runner.device)
        src_mask = src_mask.to(runner.device)
        source_length = source_length.to(runner.device)  # 将 source_length 也移到同一设备
        smiles_list = runner.sample(
            model_choice="transformer", 
            model=runner.model, 
            src=src, 
            src_mask=src_mask, 
            source_length=source_length, 
            decode_type="multinomial", 
            num_samples=num_samples
        )
        
        # 计算每个 SMILES 的化学性质
        for smiles_group in smiles_list:
            for smile in smiles_group:  # smiles_group 是一个子列表
                #链接新分子
                newsmile=connect_constVar_try(const_smiles,smile)
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


@app.get("/smiles2img")
async def smiles2img(smiles: str = Query(..., description="SMILES string of the molecule")):
    
    # 生成分子对象
    print("---开始生成分子图像--")
    print(smiles)
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"error": "Invalid SMILES string"}

    # 创建绘图对象
    drawer = Draw.MolDraw2DCairo(200, 200)
    drawer.SetFontSize(1.0)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()

    # 将绘制的图像转换为PIL图像对象
    pil_image = Image.open(io.BytesIO(drawer.GetDrawingText()))

    # 创建字节流
    strIO = BytesIO()
    pil_image.save(strIO, "PNG")
    strIO.seek(0)

    # 返回图像作为流
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
    start_time = time.time()  # 记录请求接受的时间
    try:
        # 调用 SMILES 生成逻辑
        print("/generate请求开始时间:", start_time)
        print("--------------/generate start---------------")
        result = run_generate_runner(request.constSmiles, request.varSmiles, request.mainCls, request.minorCls, request.deltaValue, request.num)
        end_time = time.time()  # 记录生成结束的时间
        duration = end_time - start_time  # 计算用时

        print("/generate请求结束时间:", end_time)
        print(f"请求处理用时: {duration:.2f}秒，本次处理分子数量为 {request.num}")
        return result
    except Exception as e:
        # 捕获异常并记录详细的错误信息，包括堆栈追踪
        error_message = f"Error occurred: {str(e)}"
        print(error_message)  # 打印到控制台，或者使用 logging 模块记录到日志文件
        raise HTTPException(status_code=500, detail=f"Error occurred: {str(e)}")