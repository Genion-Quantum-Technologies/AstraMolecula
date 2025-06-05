
from pathlib import Path
from pydantic import BaseModel
import pandas as pd
from rdkit import Chem
from rdkit.Chem import Descriptors, QED, Draw
from typing import List, Optional
import io
# 你的其他 imports 保持不变 … 
from utils.generate import GenerateRunner
from dataset import Dataset
from combine_mol import connect_constVar_try
import torch
import utils.sascorer as sascorer
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